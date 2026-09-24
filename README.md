# Agentic Data Investigation Platform
### Agentic Data Investigation Platform | Java, Spring Boot, React, Python, LangChain/LangGraph, PostgreSQL

 Setup instructions: frontend, backend, and agent

 ## Overview

 An LLM-driven platform for investigating analytical questions with auditable SQL and evidence-backed findings.

 > Why did transaction volume decline last week?

 The system compares approved data, explores hypotheses, and presents measured observations, probable root causes, limitations, investigation steps, and query evidence.

 ## Current Project Status

 The project currently includes:

 - A Next.js/React/Material UI dashboard with strict TypeScript, session history, and evidence views
- A Java 21 Spring Boot service providing the external REST API
- A Python 3.12 FastAPI/LangGraph agent service with guarded SQL execution
- PostgreSQL migrations and deterministic synthetic data
- 400 customers and 10,560 transactions covering eight fixed weeks

 The browser → Next.js → Java → Python → SQLite fixture path has been verified end to end.

 Current frontend checks: 26 tests, typecheck, and production build pass. Previous backend milestones passed 54 Java and 99 Python tests. Live PostgreSQL/Compose verification and paid-model evaluation remain outstanding.

 ## Architecture

```
Browser / Next.js + TypeScript + Material UI
  → Java 21 / Spring Boot experience service
    → Python 3.12 / LangGraph + LangChain agent service
      → Controlled tools / deterministic SQL guard
        → PostgreSQL
```

 Java owns the external REST boundary; Python owns workflow state and agent behavior. The frontend accesses Java only. Tool code owns database connectivity; the LLM never receives database credentials.

 Execution is synchronous and bounded. GET proxies result retrieval to Python. Durable persistence, streaming, and authentication are planned for later.

 ## Repository Structure

```
agentic-data-investigation/
├── frontend/
├── experience-service/
├── agent-service/
├── database/
│   ├── migrations/
│   ├── seed/
│   ├── synthetic-data/
│   └── tests/
├── docs/
│   ├── architecture.md
│   ├── agent-workflow.md
│   ├── guardrails.md
│   ├── data-scenarios.md
│   └── screenshots/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

 ## Security Model

 The database tool layer is designed to allow only structurally validated SELECT statements or safe CTEs, allowlisted relations and functions, bounded result sets, server-side timeouts, a separate read-only database identity, and audited tool execution.

 SQL is treated as untrusted input.

 Migration 002 provides restricted table grants and reader defaults. The SQL guard uses conservative structural validation and explicit SQL tools. Live PostgreSQL security verification remains outstanding.

 The `investigation_reader` role deliberately has `NOLOGIN` and no password. Future agent tools must never use the Compose bootstrap administrator.

 ## Prerequisites

 Infrastructure:

 - Git
- Docker Engine/Desktop
- Docker Compose v2

 Application:

 - Java 21
- Python 3.12
- Node.js 20.19 or newer
- npm

 The frontend uses Next.js 16.3.5, React 19.3, and Material UI 9.4, with versions pinned in `package-lock.json`. Java dependencies use Maven and Python dependencies use `requirements.lock`.

 See frontend instructions for local startup of the three application services.

 Compose uses PostgreSQL 17.11, a supported release listed on the [PostgreSQL version policy page](<https://www.postgresql.org/support/versioning/>). Patch updates should be reviewed regularly; this is the project's supported baseline rather than a claim that it is the newest major release.

 ## Run the Java API

 With Java 21 installed, run from `experience-service/`:

```
./mvnw verify
AGENT_SERVICE_BASE_URL=http://localhost:8000 ./mvnw spring-boot:run
```

 Then open [Java health](<http://localhost:8080/api/v1/health>) or use:

```
curl http://localhost:8080/api/v1/health
```

 Health returns 200 independently of Python and PostgreSQL.

 Investigation POST/GET routes use real HTTP. Without Python, they return a normalized 503. Start the Python service below to obtain a completed synthetic investigation.

 See service setup and API contracts.

 ## Run Python and Get a Completed Investigation

 Follow agent-service/README.md to create a Python 3.12 environment and install the pinned dependencies.

 From `agent-service/`, with that environment active:

```
AGENT_MODE=development SQL_BACKEND=fixture python -m uvicorn agent_service.api:create_app \
  --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

 Keep Java running with:

```
AGENT_SERVICE_BASE_URL=http://localhost:8000
```

 POST the volume-decline question to Java, then GET the returned investigation ID.

 The response contains three SQL queries, evidence, and findings showing:

 - Transaction volume declining from 1,400 to 700
- Rejected inputs increasing from 14 to 714

 This is deterministic **synthetic** analysis of June 2026 using real SQLite SQL against the committed fixture. It does not represent live business data or paid-model reasoning.

 See the integration result, agent workflow, and investigation report.

 The Python service exposes the agent routes plus compatibility aliases used by Java. The process-local result store has bounded capacity and TTL and requires a single worker. Restarting the service loses stored results.

 ## Local Database Setup

 Run these commands from the repository root:

```
cp .env.example .env
# Edit .env and set a private local POSTGRES_PASSWORD.
# Leave LLM credentials blank.
docker compose config --quiet
docker compose up -d postgres
docker compose ps
```

 On a fresh volume, PostgreSQL applies migrations, loads the seed data, and runs database assertions automatically.

 Health checks require a TCP connection plus migration and seed ledger entries. Inspect the logs if startup fails.

 The database binds to localhost and uses a persistent named volume. `docker compose down` stops the database while preserving its data.

 For a volume created by an earlier development setup, or to resume after failed initialization, run:

```
docker compose exec -T postgres sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/seed/bootstrap.sql'
```

 Applied migrations and an already-loaded dataset version are skipped. These commands do not truncate, reset, or overwrite existing records.

 Initialization scripts run only against an empty data directory. Restarting a populated volume does not automatically apply new migrations.

 See the [official PostgreSQL image initialization documentation](<https://hub.docker.com/_/postgres>) and [psql documentation](<https://www.postgresql.org/docs/17/app-psql.html>).

 Changing bootstrap environment variables does not rotate an existing database password.

 ## See the Investigation Data

 Run the six example scenarios covering volume, pipeline failures, duplicates, regional anomalies, data quality, and deployment correlation:

```
docker compose exec -T postgres sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/tests/scenarios.sql'
```

 Expected fixture results include:

 - Weekly volume falling from **1,400 to 700**
- Rejection counts increasing to **102 per run**
- **60 excess duplicate rows**
- East's declined rate increasing from **4% to 80%**
- **20 missing merchant categories**
- **10 malformed channels**

 See developer ground truth for fixed dates and interpretation.

 These are generated fixture expectations verified offline, not results from a live database run in this environment.

 For an interactive SQL session:

```
docker compose exec postgres sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

 The five tables live in the `analytics` schema. For example:

```
SELECT count(*) FROM analytics.transactions;
```

 returns 10,560 after seeding.

 From an administrator session, `SET ROLE investigation_reader;` allows exploration using the restricted identity. `RESET ROLE;` restores the session role.

 `SET ROLE` does not activate login defaults. Application tools must set read-only transactions and timeouts explicitly.

 ## Regenerate and Verify

 Python 3.12 is the project target. The standard-library-only generator and test suite also run on the available Python 3.9.

```
python3 database/synthetic-data/generate.py
python3 database/synthetic-data/generate.py --check
python3 -m unittest discover -s database/tests -v
```

 The fixed seed and dates produce byte-identical SQL and a checksum manifest.

 Regeneration updates fixture files only; it does not modify a live database. Never silently change a loaded dataset version. Follow the seed versioning instructions.

 Run the PostgreSQL scenario, constraint, and permission assertions with:

```
docker compose exec -T postgres sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/tests/verify.sql'
```

 To check repeatability, run `bootstrap.sql` twice. Both runs should complete without changing existing counts.

 SQL assertions fail with a nonzero exit code and roll back test writes.

 The health check confirms initialization ledgers, not ongoing data integrity. Run the assertions separately after database changes.

 For PostgreSQL 17 installed directly, use:

```
psql -X -v ON_ERROR_STOP=1 -d <local_database> -f database/seed/bootstrap.sql
```

 with a private administrator connection.

 Use a dedicated cluster because reader roles are cluster-wide. No database URL or password should be committed.

 ## Environment Configuration

 `.env.example` contains non-secret defaults and blank credential placeholders. `.env` and variants are ignored.

 Compose requires a nonempty local PostgreSQL password.

 `POSTGRES_HOST=postgres` is intended for future container clients. Host clients should use `localhost` and the configured `POSTGRES_PORT`.

 The fixed `investigation_reader` `NOLOGIN` role is created by migration.

 `AGENT_DB_USER` and `AGENT_DB_PASSWORD` are used by the PostgreSQL agent adapter, not by migrations. No reader credentials are generated automatically.

 `SQL_ALLOWED_TABLES` remains empty in the template; PostgreSQL mode requires an explicit list.

 The fixture backend uses its fixed five-table synthetic allowlist.

 Private model credentials are required only for production mode. Reader login provisioning is documented in the agent README.

 Do not publish full `docker compose config` output because it can contain secrets. Use `--quiet` where possible.

 ## Development Milestones

 1. Repository foundation and PostgreSQL infrastructure configuration — delivered; runtime verification pending.
2. PostgreSQL investigation schema, versioned migrations, and deterministic synthetic dataset — delivered; live database verification pending.
3. Java experience service foundation: validation, DTOs, logging, and correlation IDs — delivered and tested.
4. Python agent service, typed state, and synchronous REST contract — delivered with 70 passing tests and a real Java/Python fixture integration run.
5. Guarded database tools — conservative implementation and adversarial tests delivered; live PostgreSQL verification remains.
6. Investigation reasoning and orchestration — five diagnostic families and evidence-driven stopping delivered; live-provider evaluation remains outstanding.
7. Java/Python end-to-end integration — synchronous execution, error normalization, OpenAPI, correlation IDs, and repeatable process-level tests delivered.
8. Next.js / Material UI investigation interface — delivered with component/API tests and browser verification.
9. Investigation trace, SQL, and evidence visualization — delivered in the dashboard; richer visual analytics remain optional.
10. Observability, resilience, integration tests, application Dockerization, and portfolio polish. Authentication and durable state should be designed before public deployment.

 Current test coverage includes the previous offline dataset and Java milestones, the guarded-tool tests, agent workflow tests, and end-to-end service tests. PostgreSQL assertions still require a database runtime.

 The Java/Python integration has been verified against the deterministic fixture SQL adapter. Paid-provider and live PostgreSQL execution remain unverified.

 ## Documentation

 - Architecture and API contract
- Agent workflow
- SQL and tool guardrails
- Synthetic scenarios and expected outcomes
- Migration instructions
- Experience API contract
- Implementation reports

 ## Recent Implementation Notes

 ### Guarded Database Tools

 The database tool layer implements five controlled tools with tokenizer-based comment rejection, AST/scope policy enforcement, bound string values, and sanitized per-attempt JSON audit records.

 The existing Java API and deterministic development investigation remain compatible.

 Live PostgreSQL security verification is still outstanding; fixture and driver-mock coverage is not a substitute for that verification.

 ### Reasoning and Investigation Orchestration

 The model adapter plans relevant schema, proposes SQL, evaluates returned evidence, decides whether additional investigation is warranted, and synthesizes cited findings.

 Deterministic integration coverage includes all five question families.

 The Java GET response includes finding titles, numeric confidence, probable root cause, and evidence SQL/type/count.

 See workflow and example questions, implementation details, and the saved Java API result.

 Rebuild and restart both services to use the expanded response contract. Live PostgreSQL and paid-provider evaluations remain outstanding.

 ### End-to-End Integration

 Java and Python use synchronous execution with bounded deadlines, propagated correlation IDs, stable frontend mappings, and normalized failures.

 Both services publish OpenAPI documents.

 See integration decisions, error matrix, and test commands and the verified Java result.

 The end-to-end test starts and stops both services and exercises all five diagnostic families, agent failure, and connection outage without paid model calls.

 ### Next.js Investigation Dashboard

 The Material UI + strict TypeScript frontend supports:

 - Question submission
- Safe error handling
- Loading and cancellation
- Result summaries and confidence
- Findings linked to evidence
- SQL inspection
- Tool timelines
- Session history

 It calls Java through a configurable same-origin Next.js proxy.

 With Python running on port 8000 and Java on 8080:

```
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

 Open **http://localhost:3000**.

 See frontend setup and tests and dashboard screenshot.

 The browser displays actual backend results; no frontend fixtures are used at runtime.

 ## License

 MIT
# Agentic-Data-Investigation-Platform
