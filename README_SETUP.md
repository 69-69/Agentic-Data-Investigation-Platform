# Local setup

This guide starts the frontend, Java backend, and Python agent on your machine.
The default setup uses the included synthetic dataset and does not require PostgreSQL
or a model API key.

## Prerequisites

Install:

| Dependency | Version | Check |
| --- | --- | --- |
| Node.js and npm | Node.js 20.19 or newer | `node --version` and `npm --version` |
| Java JDK | 21 | `java --version` |
| Python | 3.12 | `python3.12 --version` |
| Docker Compose | Optional; needed for PostgreSQL | `docker compose version` |

The Java service includes a Maven wrapper, so a separate Maven installation is not required.
An internet connection is needed when installing dependencies for the first time.

Extract or clone the repository, then open a terminal in `agentic-data-investigation`.
This directory contains `frontend`, `experience-service`, `agent-service`, and
`docker-compose.yml`. Commands below assume this is your starting directory unless noted.

The commands use macOS/Linux shell syntax. Windows alternatives appear at the end.

## Service addresses

| Service | Address | Purpose |
| --- | --- | --- |
| Frontend | http://localhost:3000 | Investigation dashboard |
| Java backend | http://localhost:8080 | Frontend-facing REST API |
| Python agent | http://localhost:8000 | Investigation workflow and guarded data tools |
| PostgreSQL | localhost:5432 | Optional database backend |

Start each application service in a separate terminal and leave it running.
Start the Python agent first, then Java, then the frontend.

## 1. Set up and start the Python agent

In the first terminal:

```bash
cd agent-service
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
AGENT_MODE=development SQL_BACKEND=fixture python -m uvicorn agent_service.api:create_app \
  --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

The fixture backend loads the included synthetic dataset into SQLite and executes guarded
queries against it. Development mode supports five investigation categories: transaction
volume decline, rejected records, duplicate transactions, regional anomalies, and deployment
association. It uses fixed June–July 2026 data windows, including when a question says
“last week” or “recent.”

Check the service from another terminal:

```bash
curl http://localhost:8000/health
```

The response should show `status: UP`, `mode: development`, and
`dataSource: synthetic-sqlite`. Interactive API documentation is at
http://localhost:8000/docs.

For later starts, activate the existing virtual environment and run the Uvicorn command
again; reinstalling dependencies is unnecessary unless they have changed.

## 2. Set up and start the Java backend

In a second terminal, starting from the repository root:

```bash
cd experience-service
./mvnw verify
AGENT_SERVICE_BASE_URL=http://localhost:8000 ./mvnw spring-boot:run
```

If the wrapper is not executable after extracting the archive:

```bash
chmod +x mvnw
```

Check the backend:

```bash
curl http://localhost:8080/api/v1/health
```

The response should show `status: UP` and `service: experience-service`.
The API specification is at http://localhost:8080/openapi.json.
Health is a liveness check; a healthy Java process does not by itself confirm agent availability.

The default connection timeout is two seconds and the request deadline is 65 seconds.
Python's default workflow deadline is 60 seconds. Keep Java's deadline longer than Python's
when changing these settings.

## 3. Set up and start the frontend

In a third terminal, starting from the repository root:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Create `.env.local` only on the first setup; preserve any existing local settings.
Its default values are:

```dotenv
EXPERIENCE_API_BASE_URL=http://127.0.0.1:8080
NEXT_PUBLIC_EXPERIENCE_API_BASE_URL=/api/experience
```

Open **http://localhost:3000**.

The browser calls the same-origin Next.js API routes, which forward requests to Java.
This default setup does not need cross-origin configuration. The browser does not connect
directly to Python or the database.

`EXPERIENCE_API_BASE_URL` is server-only. `NEXT_PUBLIC_EXPERIENCE_API_BASE_URL` is visible
to the browser and embedded during the frontend build; never put secrets in a
`NEXT_PUBLIC_` variable. Restart the frontend after editing local environment settings.

## 4. Run an investigation

Select **Volume decline** and click **Run investigation**, or enter:

> Why did transaction volume decline last week?

With the default synthetic dataset, the result should include a comparison of 1,400
transactions against 700, a 50% decline, and supporting pipeline evidence.

Other supported development questions:

- What caused rejected records to spike?
- Are there duplicate transactions in the recent period?
- Which region experienced abnormal transaction behavior?
- Did a deployment correlate with a pipeline incident?

Use the result tabs to inspect findings, evidence rows, executed SQL, and tool activity.
Session history retains metadata for up to 20 investigations in the current browser tab.
The agent keeps results in memory; restarting it loses those results. Old history entries
can therefore remain visible even when the corresponding result is no longer available.

To test the REST flow without the frontend:

```bash
curl -i -X POST http://localhost:8080/api/v1/investigations \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did transaction volume decline last week?"}'
```

Copy the returned `investigationId`, then retrieve the result:

```bash
curl http://localhost:8080/api/v1/investigations/REPLACE_WITH_INVESTIGATION_ID
```

POST runs synchronously. Do not automatically repeat a timed-out submission: the server
may already have processed it, and a new POST creates another investigation. The dashboard's
**Stop waiting** action stops the browser wait, not the work on the server.

## Optional: use PostgreSQL

Docker Compose currently starts PostgreSQL only. Continue running the three application
services in their own terminals.

From the repository root, create a local configuration file if one does not already exist:

```bash
cp .env.example .env
```

Edit `.env` and set a private `POSTGRES_PASSWORD`. Keep the database name, administrator
username and port consistent with your local configuration. Do not commit `.env`.

```bash
docker compose up -d postgres
docker compose ps
docker compose logs postgres
```

On a fresh database volume, initialization applies migrations, loads synthetic data and runs
database checks. Existing volumes are preserved; restarting the container does not reset data
or automatically apply new migrations. Changing the password in `.env` does not change a
password already stored in an existing database.

Open an administrator session:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

The restricted agent role initially has no login. Set its password interactively, then enable
login:

```sql
\password investigation_reader
ALTER ROLE investigation_reader LOGIN;
\q
```

In the Python terminal, stop the existing agent and configure:

```bash
export AGENT_MODE=development
export SQL_BACKEND=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=agentic_investigation
export AGENT_DB_USER=investigation_reader
export SQL_ALLOWED_TABLES=analytics.customers,analytics.transactions,analytics.pipeline_runs,analytics.data_quality_events,analytics.deployments
```

Set `AGENT_DB_PASSWORD` privately in the process environment to the password just provisioned,
then restart Uvicorn with the same command as before, without the inline
`SQL_BACKEND=fixture` assignment. Use the reader account, never the bootstrap administrator,
for agent queries. Adjust the database name and port if you changed them.

The agent does **not** automatically load the root `.env` file. That file supplies Docker
Compose settings; export the applicable values explicitly for the Python process.
The bootstrap database checks expect the reader's initial NOLOGIN state, so that particular
assertion is not applicable unchanged after enabling runtime login.

The PostgreSQL adapter is implemented, but its live integration has not yet been verified.
The default fixture path is the verified local demonstration setup.

## Optional: enable model-backed reasoning

Configure PostgreSQL first. In the Python process environment, set:

| Variable | Value |
| --- | --- |
| `AGENT_MODE` | `production` |
| `SQL_BACKEND` | `postgres` |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | A model available to your provider account |
| `LLM_API_KEY` | Your private provider API key |

Keep the reader configuration from the PostgreSQL section, then restart the agent.
The frontend and Java configuration remain the same. Provider usage may incur charges.
Missing required settings cause startup validation to fail; the service does not silently
substitute development results. Model-backed operation has not yet been verified against
a live provider. The `production` setting selects model reasoning; it does not add
authentication, durable storage, or public-deployment controls.

## Build and test

Run each command from its indicated service directory.

### Frontend

```bash
npm run typecheck
npm test
npm run format:check
npm run build
npm run start
```

`npm run start` serves the production build on port 3000. Stop the development server first
if it is using that port.

Optional browser tests, after building the frontend:

```bash
npx playwright install chromium
npm run test:e2e
```

For browser tests against running Java and Python services:

```bash
EXPERIENCE_API_BASE_URL=http://127.0.0.1:8080 E2E_REAL_STACK=1 npm run test:e2e
```

### Java backend

```bash
./mvnw verify
```

To run the packaged application instead of Maven's development command:

```bash
AGENT_SERVICE_BASE_URL=http://localhost:8000 java -jar target/experience-service-0.1.0-SNAPSHOT.jar
```

### Python agent

With the virtual environment active:

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

After building Java, run the isolated Java/Python integration check from `agent-service`:

```bash
python tests/e2e_local.py
```

This check starts and stops its own local service processes and uses synthetic data.
Set `JAVA_HOME` or pass `--java /path/to/java` if Java 21 is not on PATH.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `AGENT_UNAVAILABLE` | Start Python and confirm Java uses `http://localhost:8000`, not the container hostname `agent-service`, for host-based runs. |
| Frontend cannot reach the API | Confirm Java is listening on 8080 and frontend `.env.local` points to it. Restart Next.js after changes. |
| `AGENT_TIMEOUT` | Check agent logs and workflow/provider timing. Avoid blindly repeating POST; the outcome may be unknown. |
| Investigation no longer available | Python may have restarted, or its retention/capacity limit removed the result. Start a new investigation. |
| Unsupported question in development mode | Use one of the five supported question categories. General model reasoning requires explicit provider and PostgreSQL configuration. |
| Port already in use | Stop the other process or select another port and update the caller's corresponding URL. |
| Java version mismatch | Point `JAVA_HOME` and PATH at JDK 21. |
| Python dependency/version errors | Recreate the virtual environment with Python 3.12 and install the locked requirements. |
| Browser tests cannot launch Chromium | Install the Playwright browser and run in an environment that permits browser processes. |
| PostgreSQL role/schema rejected | Confirm the agent uses the restricted reader, the approved tables, and the supplied migrations. Do not bypass the checks with administrator credentials. |

## Stop services

Press **Ctrl+C** in each application terminal. If using PostgreSQL:

```bash
docker compose down
```

This preserves the database volume. Avoid adding `--volumes` unless you intend to remove the
local database data.

## Windows PowerShell equivalents

Use `py -3.12` to create the virtual environment if `python3.12` is unavailable:

```powershell
cd agent-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
$env:AGENT_MODE = "development"
$env:SQL_BACKEND = "fixture"
python -m uvicorn agent_service.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

In the Java terminal, use `$env:AGENT_SERVICE_BASE_URL = "http://localhost:8000"`
and ` .\mvnw.cmd spring-boot:run` from `experience-service`.
In the frontend terminal, use `Copy-Item .env.example .env.local` on first setup, then
`npm ci` and `npm run dev`. Use `curl.exe` for curl commands to avoid older PowerShell aliases.
