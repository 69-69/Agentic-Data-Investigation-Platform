from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_service.config import Settings
from agent_service.errors import ToolError
from agent_service.tools.database import PostgresDatabase
from agent_service.tools.guard import SqlGuard


@pytest.fixture
def postgres_settings():
    return Settings(
        sql_backend="postgres",
        agent_db_password="test-only-password",
        sql_allowed_tables="analytics.transactions",
    )


def connection(unsafe=False):
    conn = AsyncMock()
    conn.__aenter__.return_value = conn

    async def execute(statement, parameters=None):
        cursor = AsyncMock()
        cursor.fetchone.return_value = (unsafe if "rolsuper" in statement else False,)
        cursor.fetchall.return_value = [("r", False, False, "id", "int8")]
        cursor.description = [SimpleNamespace(name="id")]
        cursor.fetchmany.return_value = [(1,)]
        return cursor

    conn.execute.side_effect = execute
    return conn


async def test_postgres_controls_and_bound_query(monkeypatch, postgres_settings):
    conn = connection()
    connect = AsyncMock(return_value=conn)
    monkeypatch.setattr("psycopg.AsyncConnection.connect", connect)
    tool = PostgresDatabase(postgres_settings, SqlGuard(postgres_settings.allowed_tables))
    result = await tool.execute("SELECT id FROM analytics.transactions")
    conn.set_read_only.assert_awaited_once_with(True)
    assert connect.call_args.kwargs["user"] == "investigation_reader"
    statements = [call.args[0] for call in conn.execute.call_args_list]
    assert any("'statement_timeout'" in sql for sql in statements)
    assert any("'search_path', 'pg_catalog'" in sql for sql in statements)
    assert statements[-1].endswith("LIMIT 101")
    assert result.rows == [[1]]
    assert "test-only-password" not in result.model_dump_json()
    conn.__aexit__.assert_awaited_once()


async def test_privileged_role_fails_before_candidate_execution(monkeypatch, postgres_settings):
    conn = connection(unsafe=True)
    monkeypatch.setattr("psycopg.AsyncConnection.connect", AsyncMock(return_value=conn))
    tool = PostgresDatabase(postgres_settings, SqlGuard(postgres_settings.allowed_tables))
    with pytest.raises(ToolError, match="UNSAFE_DATABASE_ROLE"):
        await tool.execute("SELECT id FROM analytics.transactions")
    assert not any("bounded_result" in call.args[0] for call in conn.execute.call_args_list)


async def test_postgres_binds_data_values(monkeypatch, postgres_settings):
    conn = connection()
    monkeypatch.setattr("psycopg.AsyncConnection.connect", AsyncMock(return_value=conn))
    tool = PostgresDatabase(postgres_settings, SqlGuard(postgres_settings.allowed_tables))
    result = await tool.execute("SELECT id FROM analytics.transactions WHERE region = 'North America'")
    statement, parameters = conn.execute.call_args.args
    assert "North America" not in statement
    assert parameters == {"p0": "North America"}
    assert "%(p0)s" in statement
    assert "'North America'" in result.sql
