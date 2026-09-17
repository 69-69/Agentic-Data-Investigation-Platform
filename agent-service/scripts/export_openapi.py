"""Export the runtime schema without starting a server or opening database/model connections."""

import json
from pathlib import Path

from agent_service.api import create_app
from agent_service.config import Settings

root = Path(__file__).resolve().parents[2]
schema = create_app(Settings(agent_mode="development", sql_backend="fixture")).openapi()
(root / "docs/openapi/agent-service.json").write_text(json.dumps(schema, indent=2) + "\n")
