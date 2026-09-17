# Spring Boot ↔ Python Integration

 ## Execution Model

 The current implementation is synchronous. Java POST waits for one Python POST while Python runs its bounded investigation and returns a terminal result.

 Java returns `201` with `investigationId`, `status`, `question`, `createdAt`, and a `Location` header. GET retrieves the retained result from Python through Java and does not start new work.

 Java does not maintain a duplicate result store, job queue, or background worker. Its existing `202` mapping is reserved for an agent response that actually reports `pending` or `running`.

 Python's default investigation deadline is 60 seconds. Java's overall request deadline is 65 seconds, including connection establishment and response decoding, with a two-second connection timeout. Java permits request deadlines up to 90 seconds. The Java deadline should remain longer than the Python workflow deadline.

 Long model calls can exhaust the Python workflow budget and produce partial or failed results. Browser and proxy timeouts should allow more than the Java request deadline.

 The current design is intended for bounded local investigations. A durable asynchronous job mechanism is required before supporting longer-running or multi-user workloads.

 There are no automatic retries or idempotency guarantees. A Java or network timeout does not establish that remote execution stopped. A timed-out POST can leave a result whose ID was never returned to the caller; repeating the request can therefore create another investigation.

 Python bounds its own execution, but an HTTP disconnect is not a distributed cancellation mechanism.

 Investigation state is process-local. Restarting Python removes retained results. By default, completed runs are retained for one hour with a capacity of 100 runs.

 ## Request Flow

```
React
  → Spring Boot POST /api/v1/investigations
    → Python POST /internal/v1/investigations
      → bounded investigation workflow
    ← Python result
  ← Java frontend DTO
```

 The request lifecycle is:

 1. React calls `/api/v1/investigations` on Spring Boot.
2. Java validates and normalizes the request and assigns or propagates a canonical UUID correlation ID.
3. Java's configured `WebClient` calls Python `/internal/v1/investigations` with `X-Correlation-Id`.
4. Python executes the investigation using the guarded database tools and emits correlated structured logs.
5. Java validates the downstream response, maps it through domain records, and returns stable frontend DTOs.
6. GET repeats the same validation and mapping for the requested investigation ID.

 `AGENT_SERVICE_BASE_URL` is environment-configured. Host-based development uses:

```
http://localhost:8000
```

 The value must be an HTTP(S) origin without credentials or paths.

 Java has no database or LLM dependency. Database access belongs to Python's tool layer.

 ## Downstream Response Validation

 Java performs structural validation before mapping Python responses into its public domain model.

 Invalid downstream responses include:

 - Malformed or oversized payloads
- Unknown investigation statuses
- Invalid timestamps
- Duplicate IDs
- Invalid evidence references
- Inconsistent evidence and query counts
- Mismatched query copies
- Incorrect investigation IDs
- Incorrect investigation questions

 SQL provenance validation performed by Java checks consistency of returned evidence. It does not execute SQL or provide SQL semantic validation.

 Private graph fields and downstream error bodies are not forwarded to the frontend.

 ## Normalized Outcomes

 | Condition | Java response |
| --- | --- |
| Terminal investigation created, including failed or partial | `201` creation envelope with `Location` |
| Retained completed, partial, or failed result | `200`; failed status includes sanitized `INVESTIGATION_FAILED` |
| Invalid public request | `400 INVALID_REQUEST` |
| Python reports missing or expired ID | `404 INVESTIGATION_NOT_FOUND` |
| Connection failure, Python `429` or `503` | `503 AGENT_UNAVAILABLE` |
| Connection/read/overall timeout, Python `504` | `504 AGENT_TIMEOUT` |
| Other Python status, empty/malformed/oversized/inconsistent response | `502 AGENT_BAD_RESPONSE` |
| Unexpected local exception | `500 INTERNAL_ERROR` |

Both services return `X-Correlation-Id`, including on errors. Java error responses contain the same correlation ID.

 Logs include service, correlation ID, outcome, and duration. They do not contain questions, SQL text, result rows, raw downstream error bodies, or credentials.

 Gateway logs record create/get operations and their mapped outcome. Each JSON log record contains the correlation ID once.

 Health endpoints are liveness checks only and remain available when the Python agent is unavailable.

 ## OpenAPI

 Java serves the frontend API contract at:

```
http://localhost:8080/openapi.json
```

 The specification is packaged at:

 Java OpenAPI specification

 Tests verify that Java DTO properties remain consistent with the public schema. Java does not include a Swagger UI dependency.

 Python serves generated OpenAPI at:

```
http://localhost:8000/openapi.json
```

 Interactive documentation is available at:

```
http://localhost:8000/docs
```

 Both public and internal compatibility routes are documented, including sanitized validation errors, correlation headers, capacity limits, and health behavior.

 The checked-in Python schema snapshot is:

 Python OpenAPI schema

 Regenerate it from `agent-service` after schema changes:

```
python scripts/export_openapi.py
```

 ## Reproducible Verification

 Build and verify Java from `experience-service`:

```
./mvnw verify
```

 Run the Python test suite and end-to-end integration test from `agent-service` with the documented Python 3.12 virtual environment active:

```
python -m pytest -q
python tests/e2e_local.py
```

 The end-to-end test requires the Maven-built Java executable JAR. Use `--jar` to specify another location and `--java /path/to/java` when Java is not on `PATH`.

 The test:

 - Starts real Java and Uvicorn processes
- Uses isolated localhost ports
- Runs all five synthetic investigation families
- Verifies public DTOs and correlation IDs
- Checks both OpenAPI endpoints
- Verifies failed-investigation mapping
- Stops Python and verifies Java returns `503`
- Verifies Java health remains available during agent outage
- Stops all child processes in cleanup

 The test uses development/fixture mode. It does not require PostgreSQL or a paid model provider.

 An optional `--output path.json` writes the verified volume-investigation result.

 Mock HTTP integration tests additionally cover:

 - Request deadlines
- Agent-unavailable and error statuses
- Malformed, empty, and oversized responses
- Redirect handling
- Investigation ID and question mismatches
- Private-field isolation
- Partial results
- Evidence consistency

 A connection-refusal test exercises a real closed local port.

 Live PostgreSQL and paid-provider integration are separate verification requirements.
