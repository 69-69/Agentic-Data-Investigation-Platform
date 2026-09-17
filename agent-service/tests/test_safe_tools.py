import asyncio
from unittest.mock import AsyncMock

import pytest

from agent_service import audit
from agent_service.errors import ToolError
from agent_service.tools.safe import SafeDatabaseTools


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE analytics.transactions",
        "WITH x AS (dElEtE FROM analytics.transactions RETURNING *) SELECT * FROM x",
        "SELECT /* nested /* UPDATE */ comment */ 1",
        "SELECT 1 -- DROP TABLE analytics.transactions",
        "/* */ SELECT 1",
        "SELECT 1/**/",
        "CALL unsafe()",
        "EXECUTE prepared_statement",
        "SELECT (SELECT pg_sleep(1))",
        "SELECT (SELECT id FROM analytics.secret LIMIT 1)",
        "WITH x AS (SELECT * FROM analytics.secret) SELECT 1",
    ],
)
def test_adversarial_parser(guard, sql):
    with pytest.raises(ToolError, match="SQL_REJECTED"):
        guard.parse(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT '-- /* DROP */' AS note",
        "sElEcT COUNT(*) FROM analytics.transactions",
        "WITH x AS (SELECT amount FROM analytics.transactions) SELECT SUM(amount) FROM x",
        "SELECT (SELECT MAX(amount) FROM analytics.transactions) AS maximum",
    ],
)
def test_legitimate_nested_and_quoted_sql(guard, sql):
    guard.parse(sql)


async def test_all_tools_and_identifier_validation(database, guard):
    tools = SafeDatabaseTools(database, guard)
    schema = await tools.get_database_schema()
    assert set(schema) == guard.tables
    metadata = await tools.get_table_metadata("analytics.transactions")
    assert "amount" in metadata["columns"]
    assert await tools.validate_sql("SELECT COUNT(*) FROM analytics.transactions") == {"valid": True}
    result = await tools.get_basic_statistics("analytics.transactions", "amount")
    assert result.columns == ["total_count", "non_null_count", "null_count", "minimum", "maximum"]
    assert result.rows[0][0] == 10560
    assert result.rows[0][0] == result.rows[0][1] + result.rows[0][2]
    result = await tools.execute_read_only_sql("SELECT id FROM analytics.transactions LIMIT 999999")
    assert len(result.rows) == 500 and result.truncated
    for table, column in [("analytics.secret", "id"), ("analytics.transactions", "amount); DROP TABLE x;--")]:
        with pytest.raises(ToolError, match="SQL_REJECTED"):
            await tools.get_basic_statistics(table, column)
    with pytest.raises(ToolError):
        await tools.get_table_metadata("pg_catalog.pg_authid")


async def test_binding_preserves_literal_semantics(database, guard):
    query = "SELECT 'x''; DROP TABLE analytics.transactions; --' AS note"
    sql, values, cap, evidence = guard.bind(query)
    assert "%(p0)s" in sql and "DROP TABLE" not in sql
    assert values == {"p0": "x'; DROP TABLE analytics.transactions; --"}
    result = await database.execute(query)
    assert result.rows == [[values["p0"]]]
    assert "DROP TABLE" in result.sql  # Evidence keeps the properly quoted data literal.
    assert cap == 100


async def test_structured_success_rejection_failure_and_cancellation(database, guard, monkeypatch):
    records = []
    monkeypatch.setattr(audit, "event", lambda name, **fields: records.append((name, fields)))
    tools = SafeDatabaseTools(database, guard)
    await tools.execute_read_only_sql("SELECT 'private-value' AS private_alias")
    with pytest.raises(ToolError):
        await tools.validate_sql("SELECT 1; DROP TABLE secret")
    broken = AsyncMock()
    broken.execute.side_effect = RuntimeError("password=do-not-leak")
    with pytest.raises(ToolError, match="TOOL_FAILED"):
        await SafeDatabaseTools(broken, guard).execute_read_only_sql("SELECT 1")
    broken.execute.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await SafeDatabaseTools(broken, guard).execute_read_only_sql("SELECT 1")
    assert [r[1]["success"] for r in records] == [True, False, False, False]
    assert [r[1]["errorType"] for r in records] == [None, "SQL_REJECTED", "TOOL_FAILED", "CANCELLED"]
    for name, record in records:
        assert name == "guarded_tool_execution"
        assert record["startTime"] <= record["endTime"]
        assert "rowCount" in record and "sanitizedArguments" in record
    assert records[0][1]["rowCount"] == 1
    assert "private-value" not in str(records) and "private_alias" not in str(records)
    assert "do-not-leak" not in str(records)


def test_log_record_includes_correlation_id(monkeypatch):
    import json
    from unittest.mock import Mock

    logger = Mock()
    monkeypatch.setattr(audit, "logger", logger)
    token = audit.correlation_id.set("test-correlation")
    try:
        audit.event("guarded_tool_execution", success=False, errorType="SQL_REJECTED")
        assert json.loads(logger.info.call_args.args[0])["correlationId"] == "test-correlation"
    finally:
        audit.correlation_id.reset(token)
