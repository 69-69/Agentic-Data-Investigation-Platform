import csv
import io
import json
import re
import sqlite3
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

import psycopg

from agent_service import audit
from agent_service.config import TABLES, Settings
from agent_service.errors import ToolError
from agent_service.models import QueryResult
from agent_service.tools.guard import SqlGuard

SCHEMA = {
    "customers": ["id", "customer_segment", "region", "created_at"],
    "transactions": [
        "id",
        "customer_id",
        "transaction_date",
        "amount",
        "transaction_type",
        "channel",
        "merchant_category",
        "region",
        "status",
        "created_at",
    ],
    "pipeline_runs": [
        "id",
        "pipeline_name",
        "started_at",
        "completed_at",
        "records_processed",
        "records_rejected",
        "status",
        "error_code",
        "error_message",
    ],
    "data_quality_events": [
        "id",
        "detected_at",
        "dataset_name",
        "issue_type",
        "severity",
        "affected_records",
        "description",
    ],
    "deployments": ["id", "service_name", "version", "deployed_at", "status"],
}


class DatabaseTool(Protocol):
    async def inspect_schema(self) -> dict[str, list[str]]: ...
    async def execute(self, candidate: str) -> QueryResult: ...
    async def close(self): ...


def bounded_result(sql, columns, raw_rows, cap):
    rows = []
    used = 0
    truncated = len(raw_rows) > cap
    for raw in raw_rows[:cap]:
        row = []
        for cell in raw:
            if isinstance(cell, (datetime, date)):
                cell = cell.isoformat()
            elif isinstance(cell, Decimal):
                cell = str(cell)  # Preserve exact decimals; no float rounding.
            if isinstance(cell, str) and len(cell.encode()) > 16384:
                cell = cell.encode()[:16384].decode(errors="ignore")
                truncated = True
            row.append(cell)
        encoded = json.dumps(row, allow_nan=False).encode()
        if used + len(encoded) > 32000:
            truncated = True
            break
        used += len(encoded)
        rows.append(row)
    if len(set(columns)) != len(columns):
        raise ToolError("DUPLICATE_RESULT_COLUMNS")
    return QueryResult(sql=sql, columns=columns, rows=rows, truncated=truncated)


class FixtureDatabase:
    """Explicit development-only SQLite adapter over the actual committed CSV/COPY fixture."""

    def __init__(self, settings: Settings, guard: SqlGuard):
        self.guard = guard
        self.timeout = settings.sql_statement_timeout_ms / 1000
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("ATTACH DATABASE ':memory:' AS analytics")
        for table, columns in SCHEMA.items():
            definition = ", ".join(
                f'"{c}" '
                + (
                    "NUMERIC"
                    if c
                    in {
                        "id",
                        "customer_id",
                        "amount",
                        "records_processed",
                        "records_rejected",
                        "affected_records",
                    }
                    else "TEXT"
                )
                for c in columns
            )
            self.connection.execute(f"CREATE TABLE analytics.{table} ({definition})")
        # Never execute fixture SQL. Read only recognized COPY payloads as CSV values.
        text = settings.fixture_path.read_text()
        blocks = re.findall(r"COPY analytics\.(\w+) \(([^)]+)\).*?;\n(.*?)\\\.\n", text, re.S)
        if len(blocks) != len(SCHEMA) or {b[0] for b in blocks} != set(SCHEMA):
            raise ValueError("Expected the committed five-table synthetic fixture")
        for table, columns, content in blocks:
            if [c.strip() for c in columns.split(",")] != SCHEMA[table]:
                raise ValueError("Unexpected fixture columns")
            rows = [
                [None if value == "\\N" else value for value in row]
                for row in csv.reader(io.StringIO(content))
            ]
            placeholders = ",".join("?" for _ in SCHEMA[table])
            self.connection.executemany(f"INSERT INTO analytics.{table} VALUES ({placeholders})", rows)
        self.connection.commit()
        self.connection.execute("PRAGMA query_only=ON")
        self.connection.set_authorizer(self._authorize)

    def _authorize(self, operation, name, column, database, source):
        if operation == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if database == "analytics" and name in TABLES else sqlite3.SQLITE_DENY
        if operation == sqlite3.SQLITE_FUNCTION:
            return (
                sqlite3.SQLITE_OK
                if column.lower() in {"count", "sum", "avg", "min", "max"}
                else sqlite3.SQLITE_DENY
            )
        if operation == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    async def inspect_schema(self):
        return {"analytics." + table: columns.copy() for table, columns in SCHEMA.items()}

    async def execute(self, candidate: str):
        sql, parameters, cap, evidence_sql = self.guard.bind(
            candidate, dialect="sqlite"
        )  # Revalidate at execution entry.
        deadline = min(time.monotonic() + self.timeout, audit.execution_deadline.get())
        self.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        try:
            cursor = self.connection.execute(sql, parameters)
            return bounded_result(
                evidence_sql, [c[0] for c in cursor.description], cursor.fetchmany(cap + 1), cap
            )
        except sqlite3.Error:
            raise ToolError("QUERY_FAILED") from None
        finally:
            self.connection.set_progress_handler(None, 0)

    async def close(self):
        self.connection.close()


class PostgresDatabase:
    def __init__(self, settings: Settings, guard: SqlGuard):
        self._settings = settings  # Never serialized into graph/model context.
        self.guard = guard

    async def _connect(self):
        s = self._settings
        connection = await psycopg.AsyncConnection.connect(
            host=s.postgres_host,
            port=s.postgres_port,
            dbname=s.postgres_db,
            user=s.agent_db_user,
            password=s.agent_db_password.get_secret_value(),
            connect_timeout=3,
        )
        await connection.set_read_only(True)
        return connection

    async def _check(self, connection):
        await connection.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (str(self._settings.sql_statement_timeout_ms),),
        )
        await connection.execute("SELECT set_config('lock_timeout', '1000', true)")
        await connection.execute("SELECT set_config('search_path', 'pg_catalog', true)")
        await connection.execute("SELECT set_config('TimeZone', 'UTC', true)")
        cursor = await connection.execute("""SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
            OR rolbypassrls OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid)
            FROM pg_roles r WHERE rolname = current_user""")
        if (await cursor.fetchone())[0]:
            raise ToolError("UNSAFE_DATABASE_ROLE")
        cursor = await connection.execute("""SELECT has_database_privilege(current_database(), 'CREATE,TEMP')
            OR has_schema_privilege('public', 'CREATE') OR has_schema_privilege('analytics', 'CREATE')""")
        if (await cursor.fetchone())[0]:
            raise ToolError("UNSAFE_DATABASE_ROLE")
        schema = {}
        for relation in sorted(self.guard.tables):
            cursor = await connection.execute(
                """SELECT c.relkind, c.relowner = (SELECT oid FROM pg_roles
                WHERE rolname = current_user), has_table_privilege(c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE'),
                a.attname, t.typname FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
                JOIN pg_attribute a ON a.attrelid = c.oid JOIN pg_type t ON t.oid = a.atttypid
                WHERE n.nspname || '.' || c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum""",
                (relation,),
            )
            rows = await cursor.fetchall()
            if not rows or any(
                row[0] != "r"
                or row[1]
                or row[2]
                or row[4] not in {"int8", "int4", "numeric", "text", "timestamptz"}
                for row in rows
            ):
                raise ToolError("UNSAFE_DATABASE_SCHEMA")
            schema[relation] = [row[3] for row in rows]
        return schema

    async def inspect_schema(self):
        try:
            async with await self._connect() as connection:
                return await self._check(connection)
        except psycopg.Error:
            raise ToolError("DATABASE_UNAVAILABLE") from None

    async def execute(self, candidate: str):
        sql, parameters, cap, evidence_sql = self.guard.bind(candidate)
        try:
            async with await self._connect() as connection:
                await self._check(connection)
                cursor = (
                    await connection.execute(sql, parameters) if parameters else await connection.execute(sql)
                )
                return bounded_result(
                    evidence_sql, [c.name for c in cursor.description], await cursor.fetchmany(cap + 1), cap
                )
        except psycopg.Error:
            raise ToolError("QUERY_FAILED") from None

    async def close(self):
        pass  # Connections are scoped to each operation; no pool/global connection is retained.
