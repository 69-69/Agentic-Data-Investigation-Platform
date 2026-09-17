import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi import Request as HttpRequest
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from agent_service import audit
from agent_service.config import Settings
from agent_service.graph import InvestigationGraph
from agent_service.models import HealthResponse, Request, Response
from agent_service.openapi import install_openapi
from agent_service.providers import DeterministicReasoner, ModelReasoner
from agent_service.service import CapacityError, InvestigationService, MemoryStore
from agent_service.tools.database import FixtureDatabase, PostgresDatabase
from agent_service.tools.guard import SqlGuard


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 16384:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds 16 KiB."},
                        "correlationId": audit.correlation_id.get(),
                    },
                )
                return await response(scope, receive, send)
            if not message.get("more_body"):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, reasoner=None, database=None):
    settings = settings or Settings()
    guard = SqlGuard(settings.allowed_tables, settings.sql_default_row_limit, settings.sql_max_row_limit)

    @asynccontextmanager
    async def lifespan(app):
        audit.configure()
        db = database or (
            FixtureDatabase(settings, guard)
            if settings.sql_backend == "fixture"
            else PostgresDatabase(settings, guard)
        )
        provider = reasoner or (
            DeterministicReasoner() if settings.agent_mode == "development" else ModelReasoner(settings)
        )
        app.state.service = InvestigationService(
            settings, InvestigationGraph(settings, db, provider, guard), MemoryStore(settings)
        )
        try:
            yield
        finally:
            await db.close()

    app = FastAPI(title="Investigation Agent Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def correlate(request: HttpRequest, call_next):
        incoming = request.headers.get("X-Correlation-Id", "")
        try:
            identity = str(UUID(incoming)) if len(incoming) == 36 else str(uuid4())
        except ValueError:
            identity = str(uuid4())
        token = audit.correlation_id.set(identity)
        start = time.monotonic()
        try:
            try:
                response = await call_next(request)
            except Exception:
                audit.event("request_failed", code="INTERNAL_ERROR")
                response = JSONResponse(
                    status_code=500,
                    content={
                        "error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed."},
                        "correlationId": identity,
                    },
                )
            response.headers["X-Correlation-Id"] = identity
            audit.event(
                "http_request", status=response.status_code, durationMs=int((time.monotonic() - start) * 1000)
            )
            return response
        finally:
            audit.correlation_id.reset(token)

    def error(status, code, message):
        return JSONResponse(
            status_code=status,
            content={
                "error": {"code": code, "message": message},
                "correlationId": audit.correlation_id.get(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exception):
        return error(
            422, "INVALID_REQUEST", "Provide a valid UUID and a nonblank question of 1–2000 characters."
        )

    @app.exception_handler(CapacityError)
    async def busy(request, exception):
        return error(503, "AGENT_BUSY", "Investigation capacity is currently full.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exception):
        return error(exception.status_code, "HTTP_ERROR", "The requested resource is unavailable.")

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return {
            "status": "UP",
            "service": "agent-service",
            "mode": settings.agent_mode,
            "dataSource": "synthetic-sqlite" if settings.sql_backend == "fixture" else "postgresql",
        }

    @app.post(
        "/internal/v1/investigations", response_model=Response, status_code=201, include_in_schema=False
    )
    @app.post("/api/v1/agent/investigations", response_model=Response, status_code=201)
    async def create(body: Request, request: HttpRequest):
        return await request.app.state.service.create(body.question, audit.correlation_id.get())

    @app.get("/internal/v1/investigations/{identity}", response_model=Response, include_in_schema=False)
    @app.get("/api/v1/agent/investigations/{identity}", response_model=Response)
    async def get(identity: UUID, request: HttpRequest):
        result = await request.app.state.service.get(identity)
        return (
            result if result else error(404, "INVESTIGATION_NOT_FOUND", "Investigation not found or expired.")
        )

    install_openapi(app)
    return app
