# Python Investigation Agent Service

 Python 3.12, FastAPI, Pydantic, LangGraph, and LangChain. The service executes a bounded investigation graph, retains per-run state in memory, and returns evidence-linked results compatible with the Java service.

 ## Run a Working Investigation Without Paid Calls

 From `agent-service/`:

```
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
AGENT_MODE=development SQL_BACKEND=fixture python -m uvicorn agent_service.api:create_app \
  --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

 Windows users can activate `.venv\Scripts\activate` and set environment variables using their shell.

 Dependencies are pinned in `pyproject.toml` and the resolved application/test lock file. No local machine paths are stored in the lock file.

 Development mode loads the committed COPY/CSV fixture into a private in-memory SQLite database. It does not execute the seed file as SQL. Guarded SELECT queries run against the loaded rows, and findings are computed from returned counts rather than hard-coded result values.

 No PostgreSQL server or API key is required for development mode.

 The deterministic scenarios cover:

 - Volume decline
- Rejection spikes
- Duplicate candidates
- Regional anomalies
- Deployment association

 The scenarios use fixed June/July 2026 UTC windows documented in the workflow and explicitly label responses as synthetic development data. Questions outside these scenarios return a failed/no-findings result rather than an invented answer.

 This mode is intended as a narrow, reproducible diagnostic path rather than a general-purpose LLM substitute.

 In a second terminal, from `experience-service/`, start Java:

```
AGENT_SERVICE_BASE_URL=http://localhost:8000 ./mvnw spring-boot:run
```

 If Java is already running with this URL, it can connect as soon as Python starts.

 A Java process configured with `http://agent-service:8000` must be restarted with `localhost` for host-based development. The container hostname is not a host DNS name.

 Submit an investigation through Java, which is the frontend-facing boundary:

```
curl -i -X POST http://localhost:8080/api/v1/investigations \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-Id: 13dc2ac8-a386-49b0-822b-3cf974965f40' \
  -d '{"question":"Why did transaction volume decline last week?"}'
```

 Copy the returned `investigationId` into:

```
GET http://localhost:8080/api/v1/investigations/<id>
```

 The deterministic fixture produces SQL-derived observations including:

 - Volume: **1,400 → 700 (50% decline)**
- Rejected records: **14 → 714**
- Ingestion deployment: **2.4.0** before the affected week

 The deployment timing is a temporal association, not proof of causation.

 An integration result is included for reference.

 ## Python Endpoints

 - `POST /api/v1/agent/investigations` — accepts `{ "question": "..." }` and returns the completed result with HTTP 201.
- `GET /api/v1/agent/investigations/{identity}` — returns the retained result, or 404 if it is missing, expired, or evicted.
- `GET /health` — reports liveness, selected mode, and data source; it does not assert PostgreSQL or model-provider readiness.
- `POST/GET /internal/v1/investigations[/{identity}]` — compatibility aliases used by the Java client and documented under the Internal Java integration OpenAPI tag.

 Interactive API documentation is available at `http://localhost:8000/docs`.

 Inputs use strict strings, strip surrounding whitespace, reject unknown fields, and enforce a 1–2000-character question limit.

 Invalid Python input and UUIDs return 422. Java's public validation returns 400.

 Request bodies are capped at 16 KiB.

 Errors use safe code/message fields. Raw driver errors, provider errors, and request values are not echoed.

 Every response includes `X-Correlation-Id`. Invalid or missing UUIDs are replaced with a generated correlation ID, and error responses include the same ID.

 Wire fields use camelCase for Java compatibility. Internal Pydantic state uses snake\_case.

 Results include the Java contract plus:

 - `currentStep`
- `steps`
- `probableRootCause`
- `confidence`
- `limitations`
- `mode`
- `dataSource`

 Java forwards probable root cause and numeric confidence, along with finding titles, confidence, evidence query, evidence type, and row count.

 Python-only diagnostic fields remain additive.

 The exact executed SQL after result bounding is returned under `sqlQueries`.

 ## Modes and Environment

 No `.env` file is loaded automatically. Export only the variables required by the selected mode and avoid sourcing the repository root environment file blindly.

 Health responses and logs identify the selected data source explicitly.

 | Variable | Default / purpose |
| --- | --- |
| `AGENT_MODE` | `development`; `production` enables the configured model |
| `SQL_BACKEND` | `fixture`; `postgres` uses the restricted PostgreSQL adapter |
| `FIXTURE_PATH` | `database/seed/synthetic-v1.sql`; override for a non-editable installation |
| `LLM_PROVIDER` | `openai`, the currently supported provider adapter |
| `LLM_MODEL`, `LLM_API_KEY` | Empty; both required for production |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` | `localhost`, `5432`, `agentic_investigation` |
| `AGENT_DB_USER` | `investigation_reader`; bootstrap identities are not accepted |
| `AGENT_DB_PASSWORD` | Private runtime password; required for PostgreSQL |
| `SQL_ALLOWED_TABLES` | Empty; an explicit comma-separated list of approved analytics tables is required for PostgreSQL |
| `SQL_DEFAULT_ROW_LIMIT`, `SQL_MAX_ROW_LIMIT` | `100` / `500` |
| `SQL_STATEMENT_TIMEOUT_MS` | `5000` |
| `INVESTIGATION_MAX_ITERATIONS` | `5` proposal calls, including rejected and completed proposals |
| `INVESTIGATION_MAX_STEPS` | `40` node visits, including synthesis |
| `INVESTIGATION_MAX_DURATION_SECONDS` | `60` total wall-clock seconds, including model, tool, and synthesis calls |
| `INVESTIGATION_RETENTION_SECONDS` | `3600` after the final update |
| `INVESTIGATION_STORE_CAPACITY` | `100` retained runs; oldest completed entry is evicted when full |
| `INVESTIGATION_MAX_CONCURRENCY` | `4` active runs; additional requests receive 503 |

`AGENT_SERVICE_PORT` in the root example is informational for host runs; pass `--port` to Uvicorn.

 Run one worker because investigation state is process-local. Restarting the service loses all investigations.

 Active runs are never evicted. TTL and capacity limits apply only to terminal runs.

 There are no background jobs or automatic retries. A synchronous timeout may leave an interrupted or partial record. Retrying the POST creates a new investigation ID.

 ## PostgreSQL Adapter

 The PostgreSQL adapter uses the restricted database identity and the migrations defined in the repository.

 Migration 002 creates the `investigation_reader` role as `NOLOGIN`. To use the adapter locally, an administrator can provision a private password and enable the role:

```
\password investigation_reader
ALTER ROLE investigation_reader LOGIN;
```

 Do not commit the password, use the bootstrap administrator for agent tools, or pass credentials through a model prompt.

 Export `AGENT_DB_PASSWORD` privately, then configure PostgreSQL mode and an explicit table allowlist:

```
export SQL_BACKEND=postgres
export SQL_ALLOWED_TABLES=analytics.transactions,analytics.pipeline_runs,analytics.deployments
```

 Development mode can use the PostgreSQL adapter without paid model calls:

```
export AGENT_MODE=development
```

 Production mode additionally requires `LLM_MODEL` and `LLM_API_KEY` and uses the LangChain OpenAI adapter with structured outputs. Other providers are not currently supported.

 No API key or paid model request is required for deterministic development mode.

 The PostgreSQL adapter:

 - Verifies the runtime role and schema privileges
- Checks ownership, base-table type, and built-in column types on each connection
- Uses read-only transactions
- Restricts the PostgreSQL function search path to `pg_catalog`
- Sets UTC and server-side statement/lock timeouts
- Performs scoped connection cleanup
- Keeps application-owned metadata queries separate from arbitrary model tools
- Rejects SQL outside the supported SELECT/CTE subset

 The general SQL parser intentionally supports a restricted subset and fails closed on unsupported syntax.

 See SQL and tool guardrails.

 PostgreSQL control-path behavior is covered with mocks, but live PostgreSQL integration has not yet been verified in this environment.

 The exercised SQL backend for deterministic investigations is SQLite.

 Before treating live model/database execution as deployment-ready, verify effective PostgreSQL permissions, timeout behavior, dialect compatibility, and cancellation against a real PostgreSQL instance.

 ## Guarded Database Tools

 `SafeDatabaseTools` is the controlled orchestration interface for schema inspection, table metadata, SQL validation, read-only execution, and basic statistics.

 The investigation graph uses these tools for schema and SQL operations.

 SQL comments are rejected by the PostgreSQL tokenizer. Nested ASTs and relation scopes are checked before execution. String values use driver parameter binding.

 The configured row limits still apply:

 - Default: 100 rows
- Maximum: 500 rows

 Each attempt produces a sanitized `guarded_tool_execution` JSON log containing the relevant execution outcome, including failures, cancellation, and correlation IDs.

 Run the full test suite with:

```
python -m pytest -q
```

 See SQL and tool guardrails for the security model and verification limits.

 ## Model Reasoning

 Production mode uses the configured LangChain model for:

 1. Planning the investigation
2. Generating candidate SQL
3. Assessing evidence after each query
4. Deciding whether additional investigation is required
5. Synthesizing the final findings

 Configure:

```
export AGENT_MODE=production
export SQL_BACKEND=postgres
export LLM_PROVIDER=openai
export LLM_MODEL=<model>
export LLM_API_KEY=<private-key>
```

 Also configure the PostgreSQL reader and SQL allowlist described above.

 There is no automatic fallback to synthetic answers when the model provider or database configuration fails.

 Do not place API keys in prompts, source files, or commits.

 The same question endpoint supports the five deterministic investigation scenarios documented in the agent workflow.

 Development mode uses fixed scenario windows. Model-driven investigations must inspect date coverage and disclose temporal assumptions.

 Final confidence values are numeric values from 0 to 1 and are not calibrated probabilities.

 ## Integration and OpenAPI

 Both agent route families are included in `/openapi.json`, and `/docs` provides interactive API documentation.

 The schema documents sanitized error envelopes and `X-Correlation-Id` headers.

 Regenerate the checked-in schema with:

```
python scripts/export_openapi.py
```

 After building Java:

```
./mvnw verify
```

 Run the local end-to-end checks from this directory with the Python virtual environment active and Java 21 on `PATH`:

```
python tests/e2e_local.py
```

 A different Java executable can be supplied with:

```
python tests/e2e_local.py --java /path/to/java
```

 The test launches isolated local servers, verifies five investigation scenarios and outage handling, and stops both servers when complete.

 See service integration and contracts.

 ## Tests and Module Boundaries

 Run:

```
python -m pytest -q
ruff check .
ruff format --check .
```

 The test suite contains 70 cases covering:

 - API input validation
- Java aliases and response shape
- Deterministic computation
- Actual SQLite execution
- SQL rejection and result limits
- Graph transitions
- Query and step budgets
- Wall-clock cancellation
- Invalid evidence references
- Retention and capacity
- Credential isolation
- PostgreSQL control calls through mocks

 Tests do not require paid model API calls.

 One upstream Starlette/AnyIO deprecation warning remains.

 Module responsibilities are:

```
api       HTTP endpoints
models    Wire models and internal state
service   Retention and bounded execution
graph     Eight-node graph and routing
providers Deterministic or model-based reasoning
tools     SQL validation and database access
config    Private runtime configuration
audit     Structured security/audit logging
```
