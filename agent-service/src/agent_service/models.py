from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from pydantic.alias_generators import to_camel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WireModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: StrictStr = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip() if isinstance(value, str) else value


class Finding(WireModel):
    id: str
    title: str = Field(default="Observation", min_length=1, max_length=160)
    confidence: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    description: str = Field(max_length=8000)
    evidence_ids: list[str] = Field(min_length=1, max_length=100)


class Evidence(WireModel):
    type: Literal["sql_result"] = "sql_result"
    query: str = ""
    row_count: int = Field(default=0, ge=0, le=500)
    id: str
    description: str
    sql_query_id: str
    columns: list[str]
    rows: list[list[Any]]


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False


class SqlQuery(WireModel):
    id: str
    sql: str
    row_count: int
    truncated: bool


class ToolExecution(WireModel):
    id: str
    tool_name: str
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int


class SafeError(WireModel):
    code: str
    message: str


class Synthesis(BaseModel):
    summary: str = Field(max_length=16000)
    findings: list[Finding] = Field(default_factory=list, max_length=10)
    probable_root_cause: str | None = Field(default=None, max_length=8000)
    confidence: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)


class InvestigationState(BaseModel):
    investigation_id: UUID
    correlation_id: str
    question: str
    current_step: str = "pending"
    schema_context: dict[str, list[str]] = Field(default_factory=dict)
    required_tables: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    evidence_sufficient: bool = False
    investigation_plan: list[str] = Field(default_factory=list)
    candidate_queries: list[str] = Field(default_factory=list)
    executed_queries: list[SqlQuery] = Field(default_factory=list)
    tool_results: list[QueryResult] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    probable_root_cause: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    errors: list[SafeError] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "partial", "failed"] = "pending"
    summary: str | None = None
    tool_executions: list[ToolExecution] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    steps: list[str] = Field(default_factory=list)
    iteration_count: int = 0
    step_count: int = 0
    approved_query: str | None = None
    stop: bool = False
    sufficient: bool = False
    limitations: list[str] = Field(default_factory=list)


class Response(WireModel):
    investigation_id: UUID
    status: Literal["pending", "running", "completed", "partial", "failed"]
    question: str
    summary: str | None
    findings: list[Finding]
    evidence: list[Evidence]
    sql_queries: list[SqlQuery]
    tool_executions: list[ToolExecution]
    created_at: datetime
    completed_at: datetime | None
    error: SafeError | None
    current_step: str
    steps: list[str]
    probable_root_cause: str | None
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    limitations: list[str]
    mode: str
    data_source: str


class HealthResponse(WireModel):
    status: Literal["UP"] = "UP"
    service: Literal["agent-service"] = "agent-service"
    mode: Literal["development", "production"]
    data_source: Literal["synthetic-sqlite", "postgresql"]
