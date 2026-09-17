from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent_service.config import Settings
from agent_service.models import InvestigationState
from agent_service.providers import ModelReasoner, Plan


def test_production_requires_explicit_database_and_provider_configuration():
    with pytest.raises(ValidationError):
        Settings(agent_mode="production")
    with pytest.raises(ValidationError):
        Settings(
            sql_backend="postgres", agent_db_password="test-only", sql_allowed_tables="pg_catalog.pg_authid"
        )
    with pytest.raises(ValidationError):
        Settings(sql_default_row_limit=500, sql_max_row_limit=100)


async def test_provider_context_excludes_private_configuration(monkeypatch):
    model = MagicMock()
    runnable = MagicMock()
    runnable.ainvoke = AsyncMock(return_value=Plan(steps=["Inspect approved data"]))
    model.with_structured_output.return_value = runnable
    monkeypatch.setattr("agent_service.providers.init_chat_model", lambda *args, **kwargs: model)
    settings = Settings(
        agent_mode="production",
        sql_backend="postgres",
        llm_model="configured-model",
        llm_api_key="test-only-model-key",
        agent_db_password="test-only-db-password",
        sql_allowed_tables="analytics.transactions",
    )
    reasoner = ModelReasoner(settings)
    await reasoner.plan("Why did volume decline?")
    messages = str(runnable.ainvoke.call_args)
    assert "test-only-model-key" not in messages and "test-only-db-password" not in messages
    state = InvestigationState(investigation_id=uuid4(), correlation_id="trace", question="question")
    assert "settings" not in reasoner._context(state)
    assert not hasattr(reasoner, "execute") and not hasattr(reasoner, "shell")


def test_startup_validation_errors_hide_credentials():
    with pytest.raises(ValidationError) as error:
        Settings(agent_mode="production", agent_db_password="never-print-this")
    assert "never-print-this" not in str(error.value)
