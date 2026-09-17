import asyncio
from uuid import uuid4

import pytest

from agent_service.config import Settings
from agent_service.graph import InvestigationGraph
from agent_service.models import Finding, InvestigationState, Synthesis
from agent_service.providers import DeterministicReasoner, Proposal
from agent_service.service import CapacityError, InvestigationService, MemoryStore

QUESTION = "Why did transaction volume decline?"


async def run(settings, database, guard, reasoner=None):
    service = InvestigationService(
        settings,
        InvestigationGraph(settings, database, reasoner or DeterministicReasoner(), guard),
        MemoryStore(settings),
    )
    result = await service.create(QUESTION, str(uuid4()))
    state = await service.store.get(result.investigation_id)
    return result, state


async def test_transitions_and_explicit_state(settings, database, guard):
    result, state = await run(settings, database, guard)
    assert state.steps[:7] == [
        "plan_investigation",
        "inspect_schema",
        "generate_query",
        "validate_query",
        "execute_query",
        "analyze_result",
        "decide_next_step",
    ]
    assert state.steps[-1] == "synthesize_findings"
    assert state.steps.count("execute_query") == 3
    assert len(state.candidate_queries) == len(state.executed_queries) == len(state.tool_results) == 3
    assert state.step_count == len(state.steps) <= settings.investigation_max_steps
    assert result.status == "completed"


class Endless(DeterministicReasoner):
    async def query(self, state):
        return Proposal(sql="SELECT COUNT(*) AS count FROM analytics.transactions")


async def test_iteration_budget(settings, database, guard):
    bounded = settings.model_copy(update={"investigation_max_iterations": 2})
    result, state = await run(bounded, database, guard, Endless())
    assert state.iteration_count == len(state.executed_queries) == 2
    assert result.status == "partial"
    assert any(e.code == "ITERATION_LIMIT" for e in state.errors)


@pytest.mark.parametrize("limit", [4, 8, 12])
async def test_step_budget(settings, database, guard, limit):
    bounded = settings.model_copy(update={"investigation_max_steps": limit})
    _, state = await run(bounded, database, guard, Endless())
    assert state.step_count <= limit
    assert state.completed_at


class Unsafe(DeterministicReasoner):
    async def query(self, state):
        return Proposal(sql="DROP TABLE analytics.transactions")


async def test_rejections_never_execute(settings, database, guard):
    _, state = await run(settings, database, guard, Unsafe())
    assert not state.executed_queries and not state.evidence
    assert state.iteration_count == settings.investigation_max_iterations
    assert any(e.code == "SQL_REJECTED" for e in state.errors)


class Slow(DeterministicReasoner):
    async def plan(self, question):
        await asyncio.sleep(10)


async def test_wall_clock_deadline(settings, database, guard):
    bounded = settings.model_copy(update={"investigation_max_duration_seconds": 0.01})
    result, state = await run(bounded, database, guard, Slow())
    assert result.status == "failed"
    assert state.completed_at
    assert state.errors[-1].code == "DEADLINE_EXCEEDED"


class Fabricator(DeterministicReasoner):
    async def synthesize(self, state):
        return Synthesis(
            summary="Unsupported", findings=[Finding(id="f1", description="Invented", evidence_ids=["fake"])]
        )


async def test_synthesis_references_are_verified(settings, database, guard):
    result, state = await run(settings, database, guard, Fabricator())
    assert not result.findings and result.status == "partial"
    assert state.errors[-1].code == "SYNTHESIS_FAILED"


async def test_store_capacity_eviction_and_active_protection():
    settings = Settings(investigation_store_capacity=1, investigation_max_concurrency=1)
    store = MemoryStore(settings)
    state = InvestigationState(investigation_id=uuid4(), correlation_id="trace", question=QUESTION)
    await store.reserve(state)
    other = state.model_copy(update={"investigation_id": uuid4()})
    with pytest.raises(CapacityError):
        await store.reserve(other)
    from agent_service.models import utcnow

    state.completed_at = utcnow()
    await store.put(state)
    await store.reserve(other)
    assert await store.get(state.investigation_id) is None
    assert await store.get(other.investigation_id)


async def test_retention_expiry_and_snapshot_isolation(monkeypatch):
    from agent_service.models import utcnow

    settings = Settings(investigation_retention_seconds=1)
    store = MemoryStore(settings)
    state = InvestigationState(
        investigation_id=uuid4(),
        correlation_id="trace",
        question=QUESTION,
        status="completed",
        completed_at=utcnow(),
    )
    await store.reserve(state)
    snapshot = await store.get(state.investigation_id)
    snapshot.question = "changed copy"
    assert (await store.get(state.investigation_id)).question == QUESTION
    import time

    now = time.monotonic()
    monkeypatch.setattr("agent_service.service.time.monotonic", lambda: now + 2)
    assert await store.get(state.investigation_id) is None


async def test_cancellation_marks_reserved_state_terminal(settings, database, guard):
    service = InvestigationService(
        settings, InvestigationGraph(settings, database, Slow(), guard), MemoryStore(settings)
    )
    task = asyncio.create_task(service.create(QUESTION, "trace"))
    while not service.store.records:
        await asyncio.sleep(0)
    identity = next(iter(service.store.records))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    state = await service.store.get(identity)
    assert state.status == "failed" and state.completed_at
    assert state.errors[-1].code == "CANCELLED"
