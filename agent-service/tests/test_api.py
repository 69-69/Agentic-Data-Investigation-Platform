from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from agent_service.api import create_app


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "  "},
        {"question": None},
        {"question": 123},
        {"question": True},
        {"question": []},
        {"question": "x" * 2001},
        {"question": "x", "sql": "DROP TABLE x"},
    ],
)
def test_invalid_api_input(client, body):
    response = client.post("/api/v1/agent/investigations", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.headers["X-Correlation-Id"] == response.json()["correlationId"]


def test_malformed_and_oversized_body(client):
    assert (
        client.post(
            "/api/v1/agent/investigations", content="{bad", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    response = client.post("/api/v1/agent/investigations", content="x" * 17000)
    assert response.status_code == 413
    assert response.headers["X-Correlation-Id"] == response.json()["correlationId"]


def test_create_get_and_java_compatibility_alias(client):
    trace = str(uuid4())
    response = client.post(
        "/internal/v1/investigations",
        json={"question": "  Why did transaction volume decline last week?  "},
        headers={"X-Correlation-Id": trace},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "completed"
    assert result["dataSource"] == "synthetic-sqlite"
    assert result["question"] == "Why did transaction volume decline last week?"
    assert response.headers["X-Correlation-Id"] == trace
    assert len(result["sqlQueries"]) == 3
    assert len(result["toolExecutions"]) == 4
    assert result["evidence"][0]["rows"] == [["2026-06-08", 1400], ["2026-06-15", 700]]
    assert result["evidence"][1]["rows"] == [["2026-06-08", 14], ["2026-06-15", 714]]
    assert "50.0%" in result["summary"]
    assert result["completedAt"] >= result["createdAt"]
    identity = result["investigationId"]
    assert client.get("/api/v1/agent/investigations/" + identity).json() == result
    assert client.get("/internal/v1/investigations/" + identity).json() == result
    assert len(response.content) < 1024 * 1024  # Java adapter limit.


def test_unknown_id_and_health(client):
    assert client.get("/api/v1/agent/investigations/" + str(uuid4())).status_code == 404
    assert client.get("/api/v1/agent/investigations/not-a-uuid").status_code == 422
    response = client.get("/health", headers={"X-Correlation-Id": "invalid"})
    assert response.status_code == 200
    UUID(response.headers["X-Correlation-Id"])
    assert response.json()["mode"] == "development"


def test_unsupported_development_question_does_not_fabricate_answer(client):
    result = client.post("/api/v1/agent/investigations", json={"question": "Predict the stock market"}).json()
    assert result["status"] == "failed"
    assert result["findings"] == result["sqlQueries"] == []
    assert result["confidence"] == 0.0


def test_deterministic_outputs_are_computed_without_model_calls(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No paid calls in development")

    monkeypatch.setattr("agent_service.providers.init_chat_model", forbidden)
    results = [
        client.post(
            "/api/v1/agent/investigations", json={"question": "Why did transaction volume decline?"}
        ).json()
        for _ in range(2)
    ]
    for key in ["summary", "evidence", "findings", "sqlQueries", "steps", "probableRootCause", "confidence"]:
        assert results[0][key] == results[1][key]
    assert results[0]["investigationId"] != results[1]["investigationId"]
