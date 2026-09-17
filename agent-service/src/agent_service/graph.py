import time

from langgraph.graph import END, START, StateGraph

from agent_service import audit
from agent_service.config import Settings
from agent_service.errors import ToolError
from agent_service.models import Evidence, InvestigationState, SafeError, SqlQuery, ToolExecution, utcnow
from agent_service.providers import Reasoner, supported
from agent_service.tools.database import DatabaseTool
from agent_service.tools.guard import SqlGuard
from agent_service.tools.safe import SafeDatabaseTools


class InvestigationGraph:
    def __init__(self, settings: Settings, database: DatabaseTool, reasoner: Reasoner, guard: SqlGuard):
        self.settings, self.database, self.reasoner, self.guard = settings, database, reasoner, guard
        self.tools = SafeDatabaseTools(database, guard)
        graph = StateGraph(InvestigationState)
        nodes = [
            "plan_investigation",
            "inspect_schema",
            "generate_query",
            "validate_query",
            "execute_query",
            "analyze_result",
            "decide_next_step",
            "synthesize_findings",
        ]
        for name in nodes:
            graph.add_node(name, self._node(name))
        graph.add_edge(START, "plan_investigation")
        for name in nodes[:-1]:
            graph.add_conditional_edges(name, self._route(name), {target: target for target in nodes})
        graph.add_edge("synthesize_findings", END)
        self.compiled = graph.compile()

    def _node(self, name):
        async def run(state: InvestigationState):
            base = {
                "current_step": name,
                "steps": state.steps + [name],
                "step_count": state.step_count + 1,
                "status": "running",
            }
            audit.event(
                "graph_node",
                investigationId=str(state.investigation_id),
                node=name,
                iteration=state.iteration_count,
            )
            if (
                name != "synthesize_findings"
                and state.step_count >= self.settings.investigation_max_steps - 2
            ):
                return base | {
                    "stop": True,
                    "errors": state.errors + [SafeError(code="STEP_LIMIT", message="Step budget exhausted.")],
                }
            try:
                return base | await getattr(self, name)(state)
            except Exception as error:
                code = error.code if isinstance(error, ToolError) else "NODE_FAILED"
                failure = SafeError(
                    code=code, message="The investigation step could not be completed safely."
                )
                return base | {"errors": state.errors + [failure], "stop": True}

        return run

    def _route(self, node):
        def route(state):
            if state.stop:
                return "synthesize_findings"
            if node == "generate_query":
                return "synthesize_findings" if state.sufficient else "validate_query"
            if node == "validate_query":
                return "execute_query" if state.approved_query else "decide_next_step"
            if node == "decide_next_step":
                return "synthesize_findings" if state.sufficient else "generate_query"
            return {
                "plan_investigation": "inspect_schema",
                "inspect_schema": "generate_query",
                "execute_query": "analyze_result",
                "analyze_result": "decide_next_step",
            }[node]

        return route

    async def plan_investigation(self, state):
        plan = await self.reasoner.plan(state.question)
        limitations = []
        if self.settings.agent_mode == "development":
            limitations.append(
                "Deterministic synthetic mode uses June 8–21 for volume/rejections/deployment, June 24–26 for duplicates, and June 29–July 12 for regions (2026 UTC); these are not current relative periods."
            )
        if self.settings.agent_mode == "development" and not supported(state.question):
            limitations.append(
                "Development mode supports only the five documented diagnostic question families."
            )
        if not set(plan.required_tables) <= self.guard.tables:
            raise ToolError("SQL_REJECTED")
        return {
            "investigation_plan": plan.steps,
            "required_tables": plan.required_tables,
            "limitations": limitations,
        }

    async def _tool(self, state, name, call, candidate=None):
        start = time.monotonic()
        outcome = "failed"
        result = None
        try:
            result = await call()
            outcome = "completed"
            return result
        finally:
            audit.event(
                "tool_execution",
                investigationId=str(state.investigation_id),
                toolName=name,
                status=outcome,
                durationMs=int((time.monotonic() - start) * 1000),
                rowCount=len(result.rows) if hasattr(result, "rows") else 0,
                **(
                    self.guard.audit(result.sql if hasattr(result, "sql") else candidate) if candidate else {}
                ),
            )

    async def inspect_schema(self, state):
        started = utcnow()
        schema = await self._tool(state, "inspect_schema", self.tools.get_database_schema)
        for table in state.required_tables:
            await self.tools.get_table_metadata(table)
        schema = {k: v for k, v in schema.items() if not state.required_tables or k in state.required_tables}
        done = utcnow()
        return {
            "schema_context": schema,
            "tool_executions": state.tool_executions
            + [
                ToolExecution(
                    id=f"t{len(state.tool_executions) + 1}",
                    tool_name="inspect_schema",
                    status="completed",
                    started_at=started,
                    completed_at=done,
                    duration_ms=max(0, int((done - started).total_seconds() * 1000)),
                )
            ],
        }

    async def generate_query(self, state):
        if state.iteration_count >= self.settings.investigation_max_iterations:
            return {
                "stop": True,
                "errors": state.errors
                + [SafeError(code="ITERATION_LIMIT", message="Query budget exhausted.")],
            }
        proposal = await self.reasoner.query(state)
        return {
            "iteration_count": state.iteration_count + 1,
            "approved_query": None,
            "sufficient": proposal.done or not proposal.sql,
            "candidate_queries": state.candidate_queries + ([proposal.sql] if proposal.sql else []),
        }

    async def validate_query(self, state):
        sql = state.candidate_queries[-1]
        try:
            await self.tools.validate_sql(sql)
            audit.event(
                "sql_validation",
                investigationId=str(state.investigation_id),
                approved=True,
                **self.guard.audit(sql),
            )
            return {"approved_query": sql}
        except ToolError:
            audit.event(
                "sql_validation",
                investigationId=str(state.investigation_id),
                approved=False,
                **self.guard.audit(sql),
            )
            return {
                "approved_query": None,
                "errors": state.errors
                + [SafeError(code="SQL_REJECTED", message="SQL policy rejected a candidate.")],
            }

    async def execute_query(self, state):
        started = utcnow()
        try:
            result = await self._tool(
                state,
                "execute_readonly_sql",
                lambda: self.tools.execute_read_only_sql(state.approved_query),
                state.approved_query,
            )
        except Exception:
            done = utcnow()
            return {
                "stop": True,
                "errors": state.errors + [SafeError(code="QUERY_FAILED", message="Read-only query failed.")],
                "tool_executions": state.tool_executions
                + [
                    ToolExecution(
                        id=f"t{len(state.tool_executions) + 1}",
                        tool_name="execute_readonly_sql",
                        status="failed",
                        started_at=started,
                        completed_at=done,
                        duration_ms=max(0, int((done - started).total_seconds() * 1000)),
                    )
                ],
            }
        done = utcnow()
        query = SqlQuery(
            id=f"s{len(state.executed_queries) + 1}",
            sql=result.sql,
            row_count=len(result.rows),
            truncated=result.truncated,
        )
        return {
            "tool_results": state.tool_results + [result],
            "executed_queries": state.executed_queries + [query],
            "tool_executions": state.tool_executions
            + [
                ToolExecution(
                    id=f"t{len(state.tool_executions) + 1}",
                    tool_name="execute_readonly_sql",
                    status="completed",
                    started_at=started,
                    completed_at=done,
                    duration_ms=max(0, int((done - started).total_seconds() * 1000)),
                )
            ],
        }

    async def analyze_result(self, state):
        result, query = state.tool_results[-1], state.executed_queries[-1]
        e = Evidence(
            id=f"e{len(state.evidence) + 1}",
            description=f"Query returned {len(result.rows)} rows.",
            sql_query_id=query.id,
            query=query.sql,
            row_count=query.row_count,
            columns=result.columns,
            rows=result.rows,
        )
        try:
            assessment = await self.reasoner.assess(
                state.model_copy(update={"evidence": state.evidence + [e]})
            )
        except Exception:
            return {
                "evidence": state.evidence + [e],
                "stop": True,
                "errors": state.errors
                + [SafeError(code="ANALYSIS_FAILED", message="Evidence retained; interpretation failed.")],
            }
        return {
            "observations": (state.observations + assessment.observations)[-20:],
            "evidence_sufficient": assessment.sufficient,
            "evidence": state.evidence + [e],
            "limitations": state.limitations
            + (
                ["A result was truncated; conclusions may require further evidence."]
                if result.truncated
                else []
            ),
        }

    async def decide_next_step(self, state):
        if state.evidence_sufficient:
            return {"sufficient": True}
        if state.iteration_count >= self.settings.investigation_max_iterations:
            return {
                "stop": True,
                "errors": state.errors
                + [SafeError(code="ITERATION_LIMIT", message="Query budget exhausted.")],
            }
        return {"sufficient": False}

    async def synthesize_findings(self, state):
        try:
            result = await self.reasoner.synthesize(state)
            ids = {e.id for e in state.evidence}
            if len({f.id for f in result.findings}) != len(result.findings) or any(
                not set(f.evidence_ids) <= ids for f in result.findings
            ):
                raise ValueError("Invalid evidence references")
            status = (
                "completed"
                if result.findings
                and not state.errors
                and not any(q.truncated for q in state.executed_queries)
                else "partial"
                if state.evidence
                else "failed"
            )
            return {
                "summary": result.summary,
                "findings": result.findings,
                "probable_root_cause": result.probable_root_cause if result.findings else None,
                "confidence": result.confidence if status == "completed" else 0.0,
                "status": status,
                "completed_at": utcnow(),
            }
        except Exception:
            return {
                "summary": (
                    "Verified query evidence is available, but synthesis could not be validated."
                    if state.evidence
                    else "No verified evidence was collected."
                ),
                "findings": [],
                "confidence": 0.0,
                "probable_root_cause": None,
                "errors": state.errors
                + [SafeError(code="SYNTHESIS_FAILED", message="Synthesis failed validation.")],
                "status": "partial" if state.evidence else "failed",
                "completed_at": utcnow(),
            }
