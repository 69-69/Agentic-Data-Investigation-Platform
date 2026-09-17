"""Only this constrained interface is used by orchestration, never a raw connection."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable

from agent_service import audit
from agent_service.errors import ToolError
from agent_service.models import utcnow
from agent_service.tools.database import DatabaseTool
from agent_service.tools.guard import SqlGuard


class SafeDatabaseTools:
    def __init__(self, database: DatabaseTool, guard: SqlGuard):
        self._database = database
        self._guard = guard

    async def _call(self, name: str, arguments: dict, action: Callable[[], Awaitable]):
        started = utcnow()
        result = None
        success = False
        error_type = None
        try:
            result = await action()
            success = True
            return result
        except asyncio.CancelledError:
            error_type = "CANCELLED"
            raise
        except Exception as error:
            error_type = error.code if isinstance(error, ToolError) else "TOOL_FAILED"
            raise ToolError(error_type) from None
        finally:
            audit.event(
                "guarded_tool_execution",
                toolName=name,
                startTime=started.isoformat(),
                endTime=utcnow().isoformat(),
                success=success,
                sanitizedArguments=arguments,
                rowCount=len(result.rows) if hasattr(result, "rows") else None,
                errorType=error_type,
            )

    async def get_database_schema(self):
        async def run():
            schema = await self._database.inspect_schema()
            return {k: v for k, v in schema.items() if k in self._guard.tables}

        return await self._call("get_database_schema", {}, run)

    async def _metadata(self, table_name):
        if table_name not in self._guard.tables:
            raise ToolError("SQL_REJECTED")
        schema = await self._database.inspect_schema()
        if table_name not in schema:
            raise ToolError("SQL_REJECTED")
        return {"table": table_name, "columns": schema[table_name]}

    @staticmethod
    def _identifier_audit(value):
        return hashlib.sha256(str(value).encode()).hexdigest()

    async def get_table_metadata(self, table_name: str):
        return await self._call(
            "get_table_metadata",
            {"tableHash": self._identifier_audit(table_name)},
            lambda: self._metadata(table_name),
        )

    async def validate_sql(self, sql: str):
        async def run():
            self._guard.parse(sql)
            return {"valid": True}

        return await self._call("validate_sql", self._guard.audit(sql), run)

    async def execute_read_only_sql(self, sql: str):
        return await self._call(
            "execute_read_only_sql", self._guard.audit(sql), lambda: self._database.execute(sql)
        )

    async def get_basic_statistics(self, table: str, column: str):
        async def run():
            metadata = await self._metadata(table)
            if column not in metadata["columns"]:
                raise ToolError("SQL_REJECTED")
            # Identifiers cannot be bound as values: validate against metadata then quote.
            relation = ".".join('"' + part.replace('"', '""') + '"' for part in table.split("."))
            field = '"' + column.replace('"', '""') + '"'
            sql = (
                f"SELECT COUNT(*) AS total_count, COUNT({field}) AS non_null_count, "
                f"COUNT(*) - COUNT({field}) AS null_count, "
                f"MIN({field}) AS minimum, MAX({field}) AS maximum FROM {relation}"
            )
            return await self._database.execute(sql)

        return await self._call(
            "get_basic_statistics",
            {"tableHash": self._identifier_audit(table), "columnHash": self._identifier_audit(column)},
            run,
        )
