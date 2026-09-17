import pytest

from agent_service.errors import ToolError


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO analytics.transactions VALUES (1)",
        "DELETE FROM analytics.transactions",
        "UPDATE analytics.transactions SET amount=0",
        "DROP TABLE analytics.transactions",
        "ALTER TABLE analytics.transactions ADD COLUMN evil text",
        "TRUNCATE analytics.transactions",
        "CREATE TABLE analytics.evil (id int)",
        "GRANT ALL ON analytics.transactions TO PUBLIC",
        "REVOKE SELECT ON analytics.transactions FROM PUBLIC",
        "COPY analytics.transactions TO STDOUT",
        "SELECT 1; DELETE FROM analytics.transactions",
        "WITH x AS (DELETE FROM analytics.transactions RETURNING *) SELECT * FROM x",
        "SELECT * FROM pg_catalog.pg_authid",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM transactions",
        "SELECT * FROM analytics.unapproved",
        "SELECT pg_sleep(1)",
        "SELECT set_config('search_path', 'public', true)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT nextval('secret_sequence')",
        "SELECT pg_advisory_lock(1)",
        "SELECT public.evil()",
        "SELECT * FROM analytics.transactions FOR UPDATE",
        "SELECT * INTO stolen FROM analytics.transactions",
        "SELECT id::regclass FROM analytics.transactions",
        "WITH RECURSIVE x AS (SELECT 1) SELECT * FROM x",
        "WITH ignored AS (SELECT * FROM pg_catalog.pg_authid) SELECT * FROM analytics.transactions",
        "SELECT * FROM analytics.transactions LIMIT -1",
        "SELECT * FROM analytics.transactions OFFSET 1000000",
        "EXPLAIN SELECT * FROM analytics.transactions",
        "SELECT current_user",
    ],
)
def test_dangerous_sql_rejected(guard, sql):
    with pytest.raises(ToolError):
        guard.prepare(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM analytics.transactions",
        "SELECT * FROM analytics.transactions LIMIT ALL",
        "WITH x AS (SELECT id FROM analytics.customers) SELECT COUNT(*) FROM x",
        "SELECT 'DROP TABLE text is data' AS note FROM analytics.customers LIMIT 1",
        "SELECT id FROM analytics.customers UNION SELECT customer_id FROM analytics.transactions",
        "SELECT c.id FROM analytics.customers c JOIN analytics.transactions t ON c.id=t.customer_id",
    ],
)
def test_safe_select_cte_union_and_join(guard, sql):
    bounded, cap = guard.prepare(sql)
    assert bounded.startswith("SELECT * FROM (")
    assert cap <= 500


async def test_real_fixture_query_limit_and_mutation_defense(database):
    result = await database.execute("SELECT id FROM analytics.transactions ORDER BY id LIMIT 999999")
    assert len(result.rows) == 500 and result.truncated
    assert result.sql.endswith("LIMIT 501")
    result = await database.execute("SELECT id FROM analytics.transactions ORDER BY id LIMIT 2")
    assert len(result.rows) == 2 and not result.truncated
    with pytest.raises(ToolError):
        await database.execute("DELETE FROM analytics.transactions")
    result = await database.execute("SELECT COUNT(*) AS count FROM analytics.transactions")
    assert result.rows == [[10560]]


def test_audit_redaction(guard):
    metadata = guard.audit("SELECT 'secret-value' AS private_alias FROM analytics.transactions")
    assert "secret-value" not in str(metadata) and "private_alias" not in str(metadata)
    assert len(metadata["sqlHash"]) == 64


async def test_sqlite_progress_timeout_obeys_run_deadline(database):
    import time

    from agent_service import audit

    token = audit.execution_deadline.set(time.monotonic() - 1)
    try:
        with pytest.raises(ToolError, match="QUERY_FAILED"):
            await database.execute(
                "SELECT COUNT(*) FROM analytics.transactions a CROSS JOIN analytics.transactions b"
            )
    finally:
        audit.execution_deadline.reset(token)
