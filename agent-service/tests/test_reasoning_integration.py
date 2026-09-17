import json
from unittest.mock import MagicMock

import pytest

from agent_service.graph import InvestigationGraph
from agent_service.models import Finding, Synthesis
from agent_service.providers import (
    DEMO_QUERIES,
    Assessment,
    DeterministicReasoner,
    ModelReasoner,
    Plan,
    Proposal,
)
from agent_service.service import InvestigationService, MemoryStore


async def investigate(settings, database, guard, question, reasoner=None):
    service = InvestigationService(
        settings,
        InvestigationGraph(settings, database, reasoner or DeterministicReasoner(), guard),
        MemoryStore(settings),
    )
    result = await service.create(question, "integration-trace")
    return result, await service.store.get(result.investigation_id)


@pytest.mark.parametrize(
    "question,columns,expected",
    [
        (
            "Why did transaction volume decline last week?",
            ["week", "volume"],
            [["2026-06-08", 1400], ["2026-06-15", 700]],
        ),
        (
            "What caused rejected records to spike?",
            ["week", "rejected"],
            [["2026-06-08", 14], ["2026-06-15", 714]],
        ),
        (
            "Are there duplicate transactions in the recent period?",
            ["duplicate_groups", "participating_rows", "excess_rows"],
            [[60, 120, 60]],
        ),
    ],
)
async def test_known_anomalies_from_executed_sql(settings, database, guard, question, columns, expected):
    result, state = await investigate(settings, database, guard, question)
    evidence = next(e for e in result.evidence if e.columns == columns)
    assert evidence.rows == expected
    assert result.status == "completed"
    assert any(evidence.id in f.evidence_ids for f in result.findings)
    assert all(f.title and 0 <= f.confidence <= 1 for f in result.findings)
    assert 0 <= result.confidence <= 1
    assert all(e.type == "sql_result" and e.query and e.row_count == len(e.rows) for e in result.evidence)
    assert state.evidence_sufficient and state.observations
    assert set(state.schema_context) == set(state.required_tables)
    assert state.step_count <= settings.investigation_max_steps


async def test_regional_controls(settings, database, guard):
    result, _ = await investigate(
        settings, database, guard, "Which region experienced abnormal transaction behavior?"
    )
    rows = {(row[1], row[0]): row[2:] for row in result.evidence[0].rows}
    assert rows["east", "baseline"] == [350, 14]
    assert rows["east", "affected"] == [350, 280]
    assert all(values == [350, 14] for (region, period), values in rows.items() if region != "east")
    assert result.status == "completed" and result.probable_root_cause is None


async def test_deployment_is_association_not_causal_proof(settings, database, guard):
    result, _ = await investigate(
        settings, database, guard, "Did a deployment correlate with a pipeline incident?"
    )
    incident = next(e for e in result.evidence if e.columns[0] == "incident_start")
    deployment = next(e for e in result.evidence if e.columns[0] == "service_name")
    assert deployment.rows[0][2] < incident.rows[0][0]
    assert incident.rows[0][2] == 714
    assert result.probable_root_cause is None
    assert result.status == "completed"


async def test_model_orchestration_uses_returned_evidence_and_stops(settings, database, guard, monkeypatch):
    calls = []

    class Structured:
        def __init__(self, schema):
            self.schema = schema

        async def ainvoke(self, messages, config):
            payload = json.loads(messages[1].content)
            calls.append((self.schema, payload, messages[0].content))
            if self.schema is Plan:
                return Plan(
                    steps=["Compare volume, then rejections."],
                    required_tables=["analytics.transactions", "analytics.pipeline_runs"],
                )
            if self.schema is Proposal:
                return Proposal(sql=DEMO_QUERIES[len(payload["evidence"])])
            if self.schema is Assessment:
                return Assessment(
                    observations=["Compare the returned weekly aggregates."],
                    sufficient=len(payload["evidence"]) == 2,
                )
            e = payload["evidence"][0]
            before, after = [row[1] for row in e["sampleRows"]]
            return Synthesis(
                summary=f"Observed change: {before} to {after}. Cause remains uncertain.",
                findings=[
                    Finding(
                        id="f1",
                        title="Volume comparison",
                        description=f"{before} to {after}",
                        confidence=0.8,
                        evidence_ids=[e["id"]],
                    )
                ],
                confidence=0.6,
            )

    model = MagicMock()
    model.with_structured_output.side_effect = Structured
    monkeypatch.setattr("agent_service.providers.init_chat_model", lambda *args, **kwargs: model)
    result, state = await investigate(
        settings, database, guard, "Why did transaction volume decline?", ModelReasoner(settings)
    )
    assert result.status == "completed" and len(result.sql_queries) == 2
    assert result.evidence[0].rows == [["2026-06-08", 1400], ["2026-06-15", 700]]
    assert [schema for schema, _, _ in calls] == [Plan, Proposal, Assessment, Proposal, Assessment, Synthesis]
    assert all("chain-of-thought" in system for _, _, system in calls)
    assert (
        "observations" not in result.model_dump()
    )  # Internal concise analysis isn't a reasoning transcript.
    assert state.evidence_sufficient


async def test_analysis_failure_retains_verified_evidence(settings, database, guard):
    class FailedAnalysis(DeterministicReasoner):
        async def assess(self, state):
            raise RuntimeError("private provider error")

    result, state = await investigate(settings, database, guard, "Why did volume decline?", FailedAnalysis())
    assert result.status == "partial" and len(result.evidence) == 1
    assert state.errors[-1].code == "ANALYSIS_FAILED"
    assert result.confidence == 0.0
    assert "private provider error" not in result.model_dump_json()


def test_repeated_literals_share_driver_parameters(guard):
    sql, params, _, _ = guard.bind(DEMO_QUERIES[0])
    # PostgreSQL must see identical expressions in SELECT and GROUP BY.
    assert len(params.values()) == len(set(params.values()))
    name = next(k for k, v in params.items() if v == "2026-06-15")
    assert sql.count(f"%({name})s") >= 2
