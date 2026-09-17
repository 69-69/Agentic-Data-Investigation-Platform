# Investigation Dashboard

 Next.js 16.3.5 App Router, React 19.3, Material UI 9.4, and strict TypeScript.

 The UI is branded **Trace**, the portfolio interface for the Agentic Data Investigation Platform.

 Dependencies are pinned and `package-lock.json` provides reproducible installation.

 ## Start Locally

 Prerequisites: Node.js 20.19 or newer with npm, plus the running Java and Python services.

 Use three terminals from the repository root.

 ### 1\. Start Python

 Use the environment described in the agent service instructions:

```
cd agent-service
source .venv/bin/activate
AGENT_MODE=development SQL_BACKEND=fixture python -m uvicorn agent_service.api:create_app \
  --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

 ### 2\. Start Java

```
cd experience-service
AGENT_SERVICE_BASE_URL=http://localhost:8000 ./mvnw spring-boot:run
```

 ### 3\. Start the Frontend

```
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

 Open **http://localhost:3000**, choose **Volume decline**, and run an investigation.

 Development results come from actual SQL executed against the synthetic fixture using fixed June/July 2026 windows. They do not represent current business data or paid-model reasoning.

 The frontend contains no hard-coded investigation results. Response fixtures are used only in tests.

 For a production frontend build:

```
npm run build
npm run start
```

 Windows users can activate the Python virtual environment and set variables using their shell, and use `mvnw.cmd` for Java.

 Keep private backend and model configuration out of frontend public variables.

 ## API Configuration and Boundaries

 | Variable | Default | Behavior |
| --- | --- | --- |
| `EXPERIENCE_API_BASE_URL` | `http://127.0.0.1:8080` | Server-only Java origin used by the fixed Next.js route handlers; can be set when starting Next.js |
| `NEXT_PUBLIC_EXPERIENCE_API_BASE_URL` | `/api/experience` | Browser API base, embedded at build time; the same-origin proxy is recommended |

The request path is:

```
Browser → Next.js route handler → Java experience service → Python agent
```

 Only Java's frontend contract crosses the proxy. Python-specific fields and raw errors are stripped.

 Database credentials and model keys must not be placed in frontend environment variables.

 Direct browser-to-Java access requires separately configured CORS and a frontend rebuild. CORS is not required with the supplied same-origin configuration.

 The proxy forwards only fixed investigation paths, with:

 - Validated UUIDs
- A 16 KiB request limit
- A 1 MiB result limit

 It never forwards cookies, authorization headers, or caller-selected upstream destinations.

 Timeouts follow the synchronous service contract:

```
Python:  60s
Java:    65s
Next.js: 67s
Browser: 70s
```

 The browser does not automatically retry POST requests.

 **Stop waiting** aborts the browser request without stopping server-side work. Retrying a failed lookup performs only GET.

 If a future agent response includes `pending` or `running`, the dashboard polls GET every two seconds for a nominal three-minute window. An in-flight bounded request can extend that window; after the polling window expires, the user can check history again.

 ## UI and State

 - `InvestigationForm` validates questions and provides five example questions.
- `LoadingState` displays elapsed waiting time without inventing graph progress.
- `ErrorState` displays safe messages and correlation IDs.
- `InvestigationStatus`, `InvestigationSummary`, and `FindingsPanel` display status, executive summary, probable cause, numeric confidence, and clickable evidence citations.
- `EvidencePanel` displays accessible, horizontally scrollable tables. Results initially show ten rows with an expand action, empty-result handling, and service truncation labels.
- `SqlEvidenceViewer` provides collapsed long queries, a scrollable code view, and a copy action with a manual-copy fallback.
- `ToolExecutionTimeline` displays recorded tool names, outcomes, duration, and timestamps. It never displays private chain-of-thought.
- Session history stores up to 20 IDs, questions, statuses, and creation times in `sessionStorage`. It survives tab reloads; evidence and results are fetched from Java and are not stored there.
- Backend expiry or restart produces a clear unavailable-result message.
- There is no list API or cross-session persistent history.
- If browser storage is blocked, the dashboard falls back to in-memory state.

 The layout uses semantic landmarks, a skip link, labeled inputs, visible focus indicators, live loading and error messages, keyboard-operable tabs/details, and mobile breakpoints.

 Confidence is explicitly an uncalibrated assessment.

 Partial and failed results are labeled, and missing evidence is never replaced with fabricated content.

 React renders server-provided text as text rather than HTML.

 ## Tests

```
npm run typecheck
npm test
npm run build
npm run format:check
```

 The 26 Vitest component, API, and proxy tests cover:

 - Question validation
- Suggestions
- Evidence citations
- Tab relationships
- Session metadata
- History restoration
- Cancellation
- Safe errors
- Request deadlines
- Correlation IDs
- Proxy destination and body policy
- Malformed payloads

 Portable Playwright scenarios are also included:

```
npx playwright install chromium
npm run build
npm run test:e2e
```

 The default browser tests use intercepted test-only responses on desktop and mobile and include axe accessibility checks.

 For the real full-stack path, start Java and Python first:

```
EXPERIENCE_API_BASE_URL=http://127.0.0.1:8080 E2E_REAL_STACK=1 npm run test:e2e
```

 Playwright starts a production Next.js server on port 3100. Override this with `FRONTEND_TEST_PORT`.

 Set `CAPTURE_SCREENSHOTS=1` to capture screenshots under `docs/screenshots`.

 The real full-stack happy path was also verified in a managed browser. Headless Chromium could not be used reliably in this environment because of sandbox restrictions, so the browser verification should not be described as a passing headless Playwright run.

 See the verification report for the exact observed checks.

 ## Screenshots

 Actual synthetic-data UI captured during browser verification:
