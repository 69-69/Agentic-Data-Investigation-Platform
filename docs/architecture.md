# Architecture contract

 The platform consists of a Next.js dashboard, Java experience API, Python investigation workflow, guarded database tools, PostgreSQL schema, and deterministic synthetic fixture generation. The local browser-to-backend fixture path is verified. Live PostgreSQL and paid-provider verification, authentication, and durable state remain outstanding.

 ## Goals and boundaries

 Separate presentation, application orchestration, investigation reasoning, and database access into independently testable modules and independently deployable services. Use explicit versioned REST DTOs, observable execution, and evidence that can be audited. Services do not share internal classes or domain models.

 | Component | Owns | Boundary |
| --- | --- | --- |
| Next.js, React, TypeScript, Material UI | Question input, progress/status, steps, SQL, evidence, and findings presentation | Calls Java only; no database access or provider secrets |
| Java 21 / Spring Boot experience service | Public API, input validation, DTO mapping, correlation IDs, normalized errors, authentication and authorization | Calls Python over internal REST; owns no analytical SQL or investigation logic |
| Python 3.12 / LangGraph + LangChain investigation service | Workflow state, planning, hypotheses, tool orchestration, evidence analysis, and synthesis | Model output is untrusted; tools own database connection adapters |
| Controlled tools within Python | Approved metadata inspection, SQL policy, read-only execution, and audit events | Only application code holds runtime database credentials |
| PostgreSQL | Synthetic analytical data in five analytics tables | Restricted reader role for application tools; separate administrator for migrations |

Java provides the stable external application boundary while investigation internals evolve. Python contains the workflow implementation using LangGraph and LangChain. Within each service, keep domain and application logic independent of REST, provider, logging, and persistence adapters.

 ## Trust and request flow

```
flowchart TD
  B[Browser / Next.js] --> J[Spring Boot public API]
  J --> P[Python internal API / LangGraph]
  P --> T[Controlled tools and SQL guard]
  T --> D[(PostgreSQL)]
  P <--> L[LLM provider: approved context only]
```

 The model provider receives only approved context and has neither database credentials nor direct database access. Database rows, questions, SQL, and tool arguments are treated as untrusted input. The Python service accesses PostgreSQL through its tool adapter; the model cannot establish database connections.

 Future deployments must restrict internal API and database network reachability. Authentication is required before public deployment.

 1. The frontend submits a question to Java. Java validates the request and creates or validates a correlation ID.
2. Java forwards the validated request and correlation ID to Python. Python assigns an investigation ID and initializes workflow state.
3. The investigation workflow obtains approved metadata, generates candidate SQL, validates it against the SQL policy, and executes only approved statements.
4. Tool results append bounded evidence and execution records. The workflow evaluates the available evidence and may perform additional bounded queries.
5. Synthesis references evidence IDs, distinguishes observations from probable explanations, and reports limitations. Java maps the result and errors; Next.js renders the status, steps, SQL, evidence, and findings.

 ## REST contracts

 The Java service exposes:

 - `POST /api/v1/investigations`
- `GET /api/v1/investigations/{id}`
- `GET /api/v1/health`

 The complete request/response shapes and error definitions are documented in experience-api.md.

 Java forwards investigation requests to Python through:

 - `POST /internal/v1/investigations`
- `GET /internal/v1/investigations/{id}`

 POST accepts a validated question and returns the investigation ID, status, question, and creation timestamp with a `Location` header. GET returns the investigation result, including summary, findings, evidence, SQL queries, tool executions, timestamps, and an optional sanitized investigation error. Correlation IDs are returned in a header on every response and in HTTP error bodies.

 The interaction is synchronous. Terminal creation results return `201`; pending/running results return `202` only when Python reports an active investigation. Java does not create background jobs, fabricate results, retry requests, or maintain a second workflow store. Python retains results in bounded process-local storage; restarting the service loses retained investigations.

 When Python is unavailable, Java returns a normalized dependency error while its health endpoint remains available. Development/fixture mode can execute the investigation workflow against the committed synthetic dataset without paid model calls.

 The default Java downstream timeout is 65 seconds, with Python's workflow budget set to 60 seconds. The frontend/proxy must allow more time than Java. Internal transport DTOs, Java domain records, and public API DTOs remain separate.

 Python supplies executed SQL and evidence references. Java validates response shape and reference integrity before exposing them. These checks protect the API contract but do not replace SQL policy enforcement or establish that an analytical conclusion is correct.

 ## State, observability, and validation

 Python owns per-run Pydantic state and retains graph state in memory with bounded capacity and TTL. The service runs with one worker because state is process-local. Durable checkpointing is not currently implemented.

 Java does not duplicate workflow state. Any future persistence layer must define retention, ownership checks, crash recovery, and safe replay behavior for tool actions.

 Use `X-Correlation-Id` throughout the request path. Accept a valid UUID or generate a new one, return it on every response, and propagate it through Java, Python, the workflow, tools, and database audit events. Incoming values are bounded and validated before entering logs.

 The investigation ID identifies a run; the correlation ID identifies the request path. Structured JSON logs contain timestamp, level, service, both IDs, duration, and outcome. Full questions, database rows, credentials, and model prompts are not logged. SQL audit records follow the redaction policy documented in the security contract.

 Tests cover DTO validation, error mapping, correlation propagation, workflow transitions and budgets, SQL policy enforcement, PostgreSQL permissions and timeouts, and end-to-end evidence rendering.

 ## Execution modes

 Development/fixture mode loads the committed synthetic dataset into a private SQLite database and executes the deterministic diagnostic against it. Responses identify the data source as synthetic development data.

 Development/PostgreSQL mode runs the same fixed-window diagnostic against an explicitly configured PostgreSQL reader.

 Production/PostgreSQL mode uses configurable LangChain structured model output for investigation planning, SQL generation, evidence assessment, and synthesis.

 No execution mode gives the model database credentials, direct database connections, shell access, or Python execution.

 See agent-service setup and investigation workflow.

 ## Frontend boundary

 The Next.js App Router frontend uses Material UI, strict TypeScript, and runtime response validation. Browser requests normally use `/api/experience/investigations`; fixed Next.js route handlers forward them to the environment-configured Java origin.

 This same-origin proxy avoids cross-origin configuration for local use and preserves the Java application boundary. Neither the browser nor Next.js connects directly to Python, PostgreSQL, or the model provider.

 Session history contains at most 20 browser-tab metadata entries. Investigation results remain owned by the Java/Python API and are fetched when needed.

 See frontend instructions.
