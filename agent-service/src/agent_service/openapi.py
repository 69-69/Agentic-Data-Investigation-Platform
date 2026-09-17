"""OpenAPI enrichment for actual middleware errors and internal compatibility routes."""

from copy import deepcopy

from fastapi.openapi.utils import get_openapi


def install_openapi(app):
    def schema():
        if app.openapi_schema:
            return app.openapi_schema
        document = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description="Synchronous bounded investigations. POST waits for terminal status. GET retrieves process-local state. No background queue; restart loses results. Health is liveness only.",
        )
        document["components"]["schemas"]["ErrorEnvelope"] = {
            "type": "object",
            "required": ["error", "correlationId"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
                },
                "correlationId": {"type": "string", "format": "uuid"},
            },
        }
        correlation = {
            "description": "Propagated or generated request UUID.",
            "schema": {"type": "string", "format": "uuid"},
        }
        for path, methods in document["paths"].items():
            for method, operation in methods.items():
                operation.setdefault("parameters", []).append(
                    {
                        "in": "header",
                        "name": "X-Correlation-Id",
                        "required": False,
                        "description": "Valid UUIDs are propagated; invalid/missing values are replaced.",
                        "schema": {"type": "string"},
                    }
                )
                codes = {413: "Request exceeds 16 KiB", 500: "Sanitized internal error"}
                if "investigations" in path:
                    codes[422] = "Invalid question or UUID; sanitized validation error"
                    if method == "post":
                        codes[503] = "Investigation capacity exhausted"
                        operation["description"] = (
                            "Waits up to the configured workflow deadline (60 seconds by default). Returns 201 for a created completed, partial or failed investigation; inspect status and error."
                        )
                    else:
                        codes[404] = "Investigation missing, expired or lost after restart"
                for code, description in codes.items():
                    operation["responses"][str(code)] = {
                        "description": description,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}
                        },
                    }
                for response in operation["responses"].values():
                    response.setdefault("headers", {})["X-Correlation-Id"] = correlation
        for suffix in ("", "/{identity}"):
            source = "/api/v1/agent/investigations" + suffix
            alias = deepcopy(document["paths"][source])
            for operation in alias.values():
                operation["operationId"] = "internal_" + operation["operationId"]
                operation["tags"] = ["Internal Java integration"]
                operation["x-internal"] = True
            document["paths"]["/internal/v1/investigations" + suffix] = alias
        app.openapi_schema = document
        return document

    app.openapi = schema
