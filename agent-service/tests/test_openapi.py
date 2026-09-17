import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_service.api import create_app


def test_openapi_matches_export_and_error_contract(settings):
    app = create_app(settings)
    spec = app.openapi()
    saved = Path(__file__).resolve().parents[2] / "docs/openapi/agent-service.json"
    assert spec == json.loads(saved.read_text())
    for prefix in ["/api/v1/agent", "/internal/v1"]:
        post = spec["paths"][prefix + "/investigations"]["post"]
        assert {"201", "422", "413", "503", "500"} <= post["responses"].keys()
        assert post["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ErrorEnvelope"
        )
        assert "X-Correlation-Id" in post["responses"]["201"]["headers"]
    with TestClient(app) as client:
        assert client.get("/openapi.json").json() == spec
        response = client.post("/internal/v1/investigations", json={"question": ""})
        assert response.status_code == 422
        assert set(response.json()) == {"error", "correlationId"}
