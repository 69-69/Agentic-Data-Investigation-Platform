from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TABLES = ("customers", "transactions", "pipeline_runs", "data_quality_events", "deployments")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None, hide_input_in_errors=True)
    agent_mode: Literal["development", "production"] = "development"
    sql_backend: Literal["fixture", "postgres"] = "fixture"
    llm_provider: Literal["openai"] = "openai"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "agentic_investigation"
    agent_db_user: Literal["investigation_reader"] = "investigation_reader"
    agent_db_password: SecretStr = SecretStr("")
    sql_allowed_tables: str = ""
    sql_default_row_limit: int = Field(default=100, ge=1, le=500)
    sql_max_row_limit: int = Field(default=500, ge=1, le=500)
    sql_statement_timeout_ms: int = Field(default=5000, ge=1, le=10000)
    investigation_max_iterations: int = Field(default=5, ge=1, le=10)
    investigation_max_steps: int = Field(default=40, ge=4, le=80)
    investigation_max_duration_seconds: float = Field(default=60, gt=0, le=60)
    investigation_retention_seconds: int = Field(default=3600, ge=1, le=86400)
    investigation_store_capacity: int = Field(default=100, ge=1, le=1000)
    investigation_max_concurrency: int = Field(default=4, ge=1, le=16)
    fixture_path: Path = Path(__file__).resolve().parents[3] / "database/seed/synthetic-v1.sql"

    @model_validator(mode="after")
    def validate_modes(self):
        if self.sql_default_row_limit > self.sql_max_row_limit:
            raise ValueError("Default row limit must not exceed maximum")
        if self.agent_mode == "production":
            if (
                self.sql_backend != "postgres"
                or not self.llm_model
                or not self.llm_api_key.get_secret_value()
            ):
                raise ValueError("Production requires PostgreSQL and an explicitly configured model/key")
        if self.sql_backend == "postgres":
            if not self.agent_db_password.get_secret_value() or not self.sql_allowed_tables.strip():
                raise ValueError("PostgreSQL requires a reader password and explicit table allowlist")
            if not self.allowed_tables <= {"analytics." + name for name in TABLES}:
                raise ValueError("Only approved analytical base tables may be enabled")
        return self

    @property
    def allowed_tables(self) -> set[str]:
        if self.sql_backend == "fixture":
            return {"analytics." + name for name in TABLES}
        return {name.strip() for name in self.sql_allowed_tables.split(",") if name.strip()}
