import asyncio
import time
from collections import OrderedDict
from uuid import UUID, uuid4

from agent_service import audit
from agent_service.config import Settings
from agent_service.graph import InvestigationGraph
from agent_service.models import InvestigationState, Response, SafeError, utcnow


class CapacityError(Exception):
    pass


class MemoryStore:
    """Single-process bounded state retention; no restart durability is implied."""

    def __init__(self, settings):
        self.settings = settings
        self.records = OrderedDict()
        self.lock = asyncio.Lock()

    def _prune(self):
        now = time.monotonic()
        for key, (updated, state) in list(self.records.items()):
            if state.completed_at and now - updated >= self.settings.investigation_retention_seconds:
                del self.records[key]

    async def reserve(self, state):
        async with self.lock:
            self._prune()
            active = sum(item[1].completed_at is None for item in self.records.values())
            if active >= self.settings.investigation_max_concurrency:
                raise CapacityError()
            if len(self.records) >= self.settings.investigation_store_capacity:
                victim = next((key for key, (_, s) in self.records.items() if s.completed_at), None)
                if victim is None:
                    raise CapacityError()
                del self.records[victim]
            self.records[state.investigation_id] = (time.monotonic(), state.model_copy(deep=True))

    async def put(self, state):
        async with self.lock:
            self.records[state.investigation_id] = (time.monotonic(), state.model_copy(deep=True))

    async def get(self, identity):
        async with self.lock:
            self._prune()
            item = self.records.get(identity)
            return item[1].model_copy(deep=True) if item else None


class InvestigationService:
    def __init__(self, settings: Settings, graph: InvestigationGraph, store: MemoryStore):
        self.settings, self.graph, self.store = settings, graph, store

    async def create(self, question: str, correlation: str):
        state = InvestigationState(investigation_id=uuid4(), correlation_id=correlation, question=question)
        await self.store.reserve(state)
        token = audit.execution_deadline.set(
            time.monotonic() + self.settings.investigation_max_duration_seconds
        )
        try:
            async with asyncio.timeout(self.settings.investigation_max_duration_seconds):
                async for snapshot in self.graph.compiled.astream(
                    state,
                    stream_mode="values",
                    config={"recursion_limit": self.settings.investigation_max_steps + 5},
                ):
                    state = InvestigationState.model_validate(snapshot)
                    await self.store.put(state)
        except asyncio.CancelledError:
            state = self._interrupt(state, "CANCELLED")
            await self.store.put(state)
            raise
        except TimeoutError:
            state = self._interrupt(state, "DEADLINE_EXCEEDED")
        except Exception:
            state = self._interrupt(state, "WORKFLOW_FAILED")
        finally:
            audit.execution_deadline.reset(token)
        if state.completed_at is None:
            state = self._interrupt(state, "WORKFLOW_INCOMPLETE")
        await self.store.put(state)
        return self.response(state)

    def _interrupt(self, state, code):
        return state.model_copy(
            update={
                "status": "partial" if state.evidence else "failed",
                "completed_at": utcnow(),
                "current_step": "interrupted",
                "confidence": 0.0,
                "probable_root_cause": None,
                "summary": "The workflow stopped; only collected evidence is available.",
                "findings": [],
                "errors": state.errors + [SafeError(code=code, message="Workflow stopped safely.")],
            }
        )

    async def get(self, identity: UUID):
        state = await self.store.get(identity)
        return self.response(state) if state else None

    def response(self, state):
        return Response(
            investigation_id=state.investigation_id,
            status=state.status,
            question=state.question,
            summary=state.summary,
            findings=state.findings,
            evidence=state.evidence,
            sql_queries=state.executed_queries,
            tool_executions=state.tool_executions,
            created_at=state.created_at,
            completed_at=state.completed_at,
            error=(
                state.errors[-1]
                if state.errors
                else SafeError(code="NO_FINDINGS", message="No supported conclusion was established.")
            )
            if state.status == "failed"
            else None,
            current_step=state.current_step,
            steps=state.steps,
            probable_root_cause=state.probable_root_cause,
            confidence=state.confidence,
            limitations=state.limitations + [e.message for e in state.errors],
            mode=self.settings.agent_mode,
            data_source="synthetic-sqlite" if self.settings.sql_backend == "fixture" else "postgresql",
        )
