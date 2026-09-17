# Experience API Contract

 The Java 21 / Spring Boot experience service implements this public API. Python is accessed through a real configurable HTTP integration; agent mocks are used only by tests under `src/test`.

 Java has no SQL implementation, database client, or LLM SDK. Database access and model execution remain within the Python service.

 ## Lifecycle and Ownership

 Each Java POST makes one bounded Python POST. Python supplies the investigation ID, question, status, and timestamps. Java validates and maps the response before returning a creation envelope.

 Terminal investigations return **201**. If Python actually reports `pending` or `running`, Java returns **202**. Java does not create or schedule background work.

 Both responses include:

```
Location: /api/v1/investigations/{id}
```

 Each Java GET calls Python GET for the same investigation ID. Java does not maintain a duplicate investigation repository.

 Python retains investigation state in process memory for a bounded lifetime. The default retention period is one hour. Restarting Python removes retained investigations.

 Durable persistence, restart survival, authenticated ownership, pagination, and idempotency are not currently implemented.

 When Python is unavailable, Java returns a normalized dependency error.

 There are no automatic retries. A timeout does not establish that remote execution stopped; a timed-out POST may already have created a remote investigation whose ID was never returned to the caller. Retrying the request can therefore create another investigation.

 ## Public Endpoints

 ### Create an Investigation

 `POST /api/v1/investigations`

 Content type:

```
application/json
```

 Request:

```
{
  "question": "Why did transaction volume decline last week?"
}
```

 `question` must be a string. Leading and trailing whitespace is removed before validation.

 Bean Validation requires:

 - 1–2000 Java characters
- Nonblank content

 Missing, null, blank, or oversized questions, unknown request properties, malformed JSON, and non-string scalar values return `400 INVALID_REQUEST` without calling Python.

 Example creation response:

```
{
  "investigationId": "11db2b38-a18a-42da-a32b-1f192d66caa1",
  "status": "completed",
  "question": "Why did transaction volume decline last week?",
  "createdAt": "2026-06-22T01:00:00Z"
}
```

 The creation response contains the investigation ID and lifecycle metadata. Full results are retrieved with GET.

 ### Retrieve an Investigation

 `GET /api/v1/investigations/{id}`

 The path parameter must be a UUID.

 Example:

```
{
  "investigationId": "11db2b38-a18a-42da-a32b-1f192d66caa1",
  "status": "completed",
  "question": "Why did transaction volume decline last week?",
  "summary": "Example summary, supplied by the agent.",
  "probableRootCause": "Example probable cause.",
  "confidence": 0.72,
  "findings": [],
  "evidence": [],
  "sqlQueries": [],
  "toolExecutions": [],
  "createdAt": "2026-06-22T01:00:00Z",
  "completedAt": "2026-06-22T01:00:02Z",
  "error": null
}
```

 Arrays are always present, including when empty.

 ### Health

 `GET /api/v1/health`

 Response:

```
{
  "status": "UP",
  "service": "experience-service"
}
```

 Health is a liveness check. It does not verify Python or PostgreSQL availability and remains available when the agent service is down.

 ## Result Types

 ### Findings

 Each finding contains:

```
id
title
description
confidence
evidenceIds
```

 `confidence` is numeric and constrained to `0–1`.

 `evidenceIds` contains references to evidence records in the same investigation.

 ### Evidence

 Each evidence record contains:

```
id
description
type
sqlQueryId
query
columns
rows
```

 The current SQL evidence type is `sql_result`.

 `rows` contains arrays of JSON cells. Null database values are represented as JSON `null`.

 ### SQL Queries

 Each query record contains:

```
id
sql
rowCount
truncated
```

 `rowCount` is constrained to `0–500`.

 The returned SQL is the executed, bounded statement associated with the evidence.

 ### Tool Executions

 Each tool execution contains:

```
id
toolName
status
startedAt
completedAt
durationMs
```

 `status` is either `completed` or `failed`.

 `durationMs` is nonnegative.

 Tool execution records expose observable tool activity but do not expose private model reasoning or chain-of-thought.

 ## Result Validation

 Each result list is bounded to 100 records. Each evidence item contains at most 500 rows.

 The decoded downstream response is capped at 1 MiB.

 Java validates:

 - Unique IDs within each result collection
- Evidence references
- Finding references
- SQL query references
- Evidence row widths
- Copied SQL consistency
- Query row counts
- Investigation ID consistency
- Investigation question consistency
- Valid timestamps
- Valid status values
- Confidence ranges
- Payload size

 These checks enforce response structure and provenance. They do not establish the correctness of the agent's analysis or provide SQL security validation.

 Investigation status is one of:

```
pending
running
completed
partial
failed
```

 Active results have a null `completedAt`.

 Terminal results require `completedAt` to be at or after `createdAt`.

 A failed investigation remains a retrievable resource and returns `200` with a sanitized error:

```
{
  "code": "INVESTIGATION_FAILED",
  "message": "The investigation could not be completed."
}
```

 Dependency and protocol failures use HTTP error responses instead.

 `summary`, `probableRootCause`, and other additive analytical fields may be null when unavailable.

 Older agent responses may omit additive fields. Missing numeric confidence is mapped to `0`; evidence SQL and row counts are derived from the linked query records where available.

 ## Internal Python Contract

 The Java adapter calls:

```
POST /internal/v1/investigations
GET  /internal/v1/investigations/{id}
```

 POST accepts:

```
{
  "question": "Why did transaction volume decline last week?"
}
```

 Successful responses contain the full investigation result shape.

 POST must return the normalized question. GET must return the requested investigation ID.

 Unknown top-level agent fields are ignored so Python can add private metadata without changing the Java public contract. Required and typed result fields are validated.

 Secrets must not appear in response fields.

 Internal wire records are private to the adapter package. They map first to Java application/domain records and then to separate public API records. Python graph-state types therefore do not become part of the browser contract.

 Detailed workflow information is currently represented through observable tool execution records. Any richer trace contract should be versioned separately.

 Python also exposes compatibility routes under:

```
/api/v1/agent/investigations
```

 and a `/health` endpoint. These are not part of the public browser-facing Java API.

 ## Correlation and Error Handling

 Every response carries `X-Correlation-Id`.

 A valid UUID correlation header is propagated to Python. Missing or invalid values are replaced with a generated UUID.

 The correlation ID is a tracing identifier. It is not an authorization credential or investigation ID.

 Error responses contain the same correlation ID:

```
{
  "error": {
    "code": "AGENT_UNAVAILABLE",
    "message": "The investigation service is unavailable."
  },
  "correlationId": "13dc2ac8-a386-49b0-822b-3cf974965f40"
}
```

 | Condition | HTTP / code |
| --- | --- |
| Invalid request body or UUID | `400 / INVALID_REQUEST` |
| Agent GET returns 404 | `404 / INVESTIGATION_NOT_FOUND` |
| Connection failure, agent 429 or 503 | `503 / AGENT_UNAVAILABLE` |
| Overall deadline, read timeout, or agent 504 | `504 / AGENT_TIMEOUT` |
| Other downstream status, malformed/oversized body, invalid references, or ID/question mismatch | `502 / AGENT_BAD_RESPONSE` |
| Unexpected local exception | `500 / INTERNAL_ERROR` |

Framework-level `404`, `405`, and `415` responses retain the appropriate HTTP status and use safe error codes.

 Error normalization never forwards downstream bodies, stack traces, URLs, credentials, or provider error messages.

 No retries are enabled, including connection retries in Reactor Netty.

 ## Logging

 Spring Boot Logstash JSON is used for structured application logs.

 The servlet filter sets and removes correlation information in MDC within a `finally` block.

 Logs contain operational metadata such as:

 - Service
- Correlation ID
- Outcome
- Duration
- HTTP status

 Successful investigation mappings may also record the investigation ID and status.

 This service does not log:

 - Questions
- Result rows
- SQL text
- Raw downstream error bodies
- Credentials

 SQL audit records are owned by the controlled Python database tools.

 ## HTTP Configuration

 `AGENT_SERVICE_BASE_URL` configures the Python service origin.

 For host-based development:

```
AGENT_SERVICE_BASE_URL=http://localhost:8000
```

 The configured value must be an HTTP(S) origin without credentials or paths.

 The current timeout configuration is:

```
AGENT_CONNECT_TIMEOUT=2s
AGENT_REQUEST_TIMEOUT=65s
```

 The request timeout includes connection and response decoding and must remain within the configured service limit.

 Python's default investigation budget is 60 seconds, leaving a small amount of additional time in the Java request budget for HTTP processing.

 ## Current Deployment Boundaries

 The API currently has no:

 - Authentication
- Durable state
- Rate limiting
- Streaming
- Cross-user ownership model
- Implicit CORS configuration

 The supplied frontend uses a same-origin Next.js proxy.

 Cross-origin browser access requires an explicitly configured and reviewed CORS policy.

 Production deployment requires authentication and ownership checks. Production ingress should also enforce request-body and concurrency limits.

 ## OpenAPI

 The public Java contract is published at:

```
http://localhost:8080/openapi.json
```

 The packaged specification is maintained at:

 Java OpenAPI specification

 Tests verify public DTO properties against the schema.

 The Java service does not include a Swagger UI dependency.

 The Python service publishes its own generated OpenAPI contract and interactive documentation separately.

 ## Verification

 The Java test suite covers:

 - Request validation
- Downstream success and error statuses
- Malformed and oversized responses
- Evidence references
- Response consistency
- Timeouts without retries
- Correlation propagation and cleanup
- Structured logging
- Health independence
- Private-field isolation

 The real-process integration test exercises Java and Python together using the deterministic fixture backend, including the five supported investigation families, failure handling, correlation propagation, and OpenAPI endpoints.

 Live PostgreSQL and paid-provider integration are separate verification requirements.
