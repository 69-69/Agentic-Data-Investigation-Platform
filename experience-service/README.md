# Experience Service

 Java 21, Spring Boot 4.1.1, Spring MVC, Bean Validation, Jackson 3, and WebClient. The service uses a real HTTP adapter to call Python; stub responses are used only in tests. No PostgreSQL or LLM dependency is required to start Java.

 ## Build and Run

 Install a Java 21 JDK and set `JAVA_HOME`.

 The committed Maven wrapper pins Maven 3.9.11 and verifies the distribution with SHA-256. Its first run requires network access.

 Run from `experience-service/`:

```
./mvnw verify
AGENT_SERVICE_BASE_URL=http://localhost:8000 ./mvnw spring-boot:run
```

 On Windows, use `mvnw.cmd` and set environment variables using your shell.

 Alternatively, run the built executable:

```
java -jar target/experience-service-0.1.0-SNAPSHOT.jar
```

 Compose currently manages PostgreSQL only; application Dockerization is not included yet.

 Spring Boot does not automatically read the root `.env` file. Export Java settings or provide command-line overrides. Do not load database or LLM secrets into this service.

 ## Configuration

 | Environment variable | Default | Meaning |
| --- | --- | --- |
| `EXPERIENCE_SERVICE_PORT` | `8080` | Java HTTP port |
| `AGENT_SERVICE_BASE_URL` | `http://localhost:8000` | Python HTTP(S) origin; credentials, path, query, and fragment are rejected |
| `AGENT_CONNECT_TIMEOUT` | `2s` | Connection establishment budget |
| `AGENT_REQUEST_TIMEOUT` | `65s` | Total downstream request budget, including response consumption |
| `LOG_LEVEL` | `INFO` | JSON log level |

Timeouts must be positive. The connection budget cannot exceed the request budget, and the request budget cannot exceed 90 seconds.

 The normal request budget should remain above Python's 60-second investigation limit, with the browser/proxy timeout above Java's budget.

 The root environment example uses `http://agent-service:8000` for container networking. Use `localhost` when running both services directly on the host.

 ## Verify the Service

 With Java running, use:

```
curl -i http://localhost:8080/api/v1/health
```

 Submit an investigation:

```
curl -i -X POST http://localhost:8080/api/v1/investigations \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-Id: 13dc2ac8-a386-49b0-822b-3cf974965f40' \
  -d '{"question":"Why did transaction volume decline last week?"}'
```

 Then retrieve the returned investigation ID:

```
curl -i http://localhost:8080/api/v1/investigations/<investigation-id>
```

 Health returns 200 independently of the Python agent.

 If Python is unavailable, investigation requests return 503 with `AGENT_UNAVAILABLE` rather than synthetic or fictional results. Start the agent service to run SQL-backed synthetic investigations through these endpoints.

 POST returns the run ID, status, question, and creation time. GET retrieves the current result.

 A missing agent does not prevent Java from starting or cause the health endpoint to fail.

 ## Modules

 - `api` — REST controllers, public DTOs, input validation, correlation filter, and exception mapping.
- `application` — investigation service and `AgentGateway` port.
- `domain` — Java-owned result types.
- `adapter/agent` — WebClient transport, internal DTO validation, and domain mapping.
- `config` — validated agent properties and strict JSON scalar handling.

 Java does not retain investigation workflow state.

 See the API contract for lifecycle, nested evidence shapes, and error codes.

 ## Tests and Verification

 `./mvnw verify` runs unit and service tests plus Spring Boot/MockMvc tests backed by a test-only real HTTP server.

 The tests cover:

 - Downstream success and error statuses
- Request validation
- Malformed and oversized responses
- Evidence references
- Timeouts without retries
- Correlation ID propagation and cleanup
- Structured logging
- Health independence

 No Python, Docker, database, or LLM key is required to run the test suite.

 Test fixtures are stored only under `src/test`.

 The current test suite contains 42 tests with zero failures, errors, or skips on Java 21.

 The executable JAR has also been smoke-tested with the agent unavailable: health returns 200, investigation requests return 503, and correlation IDs are preserved.

 See the implementation report.

 References: [Spring Boot requirements](<https://docs.spring.io/spring-boot/system-requirements.html>) and [Spring Boot structured logging](<https://docs.spring.io/spring-boot/reference/features/logging.html>).

 Dependencies and plugin versions are managed through the pinned Spring Boot parent.

 ## Integration Contract

 The frontend-facing OpenAPI document is served at `/openapi.json` and packaged from `src/main/resources/static/openapi.json`. DTO-property tests guard against schema drift.

 Execution remains synchronous, with a 65-second Java request deadline around Python's 60-second workflow budget.

 Failed investigations remain retrievable resources. Transport and protocol errors are normalized separately.

 There are no automatic retries and no duplicate Java-side state store.

 After updating either service, rebuild and restart it before testing the integration path.

 For the real-process integration test, build Java with:

```
./mvnw verify
```

 Then activate the agent-service virtual environment and run:

```
python tests/e2e_local.py
```

 Run that command from `agent-service/`.

 See service integration for the complete request flow, error handling, and design tradeoffs.
