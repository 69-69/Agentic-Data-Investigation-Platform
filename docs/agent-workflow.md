# Investigation workflow

 The Python service runs a compiled LangGraph `StateGraph` with explicit Pydantic state. The configured LangChain model produces structured plans, SQL proposals, evidence assessments, and final findings. It has no database connection, credentials, or arbitrary code tools. Development mode uses a separate deterministic reasoner implementing the same interface.

 Mermaid flowchart: START, plan\_investigation, inspect\_schema, generate\_query, validate\_query, synthesize\_findings, execute\_query, decide\_next\_step, analyze\_result, END

## Node responsibilities

 | Node | Behavior |
| --- | --- |
| `plan_investigation` | Produces up to five concise investigation actions and selects required tables. Table selection is validated against the application allowlist. |
| `inspect_schema` | Calls the guarded schema and table-metadata tools and retains the selected approved columns. |
| `generate_query` | Provides the question, plan, selected schema, prior queries, observations, evidence samples, limitations, and remaining budget to the reasoner. The reasoner returns one candidate query or indicates that no additional query is needed. |
| `validate_query` | Applies the SQL tokenizer, AST, function, and relation-scope policy. Rejected SQL is never executed. |
| `execute_query` | Revalidates the candidate and executes it through the guarded database tools with row/time limits and parameter binding. Bounded SQL and returned rows are retained as evidence. |
| `analyze_result` | Attaches an evidence ID, query, type, and row count. The reasoner produces concise observations and assesses whether the available evidence is sufficient. Evidence is retained even if this assessment fails. |
| `decide_next_step` | Stops when the evidence is sufficient; otherwise continues while the investigation budget remains. |
| `synthesize_findings` | Produces finding titles, descriptions, numeric confidence, and evidence citations. Finding IDs must be unique and every cited evidence ID must exist. |

The reasoning interface separates observations from inference and requires uncertainty to be reported when evidence is incomplete. The workflow does not request or return private chain-of-thought. Reference validation verifies provenance and structure; it does not establish that arbitrary model-generated prose is factually correct.

 ## State and execution limits

 State contains the investigation and correlation IDs, question, current step, selected tables, schema, plan, candidate and executed queries, tool results, evidence, concise observations, evidence sufficiency, findings, probable cause, confidence, errors, status, and timestamps.

 Credentials and provider configuration remain outside workflow state.

 Default execution limits are:

 - Five query proposals
- 40 graph node visits
- 60 seconds total execution time
- 500 rows per query, with a 100-row default
- 32,000 data bytes per query
- 16 KiB per cell
- Four concurrent investigations
- 100 retained terminal investigations
- One-hour terminal retention

 Rejected queries consume proposal budget. A sufficiency decision can terminate the workflow without generating an additional `done` proposal.

 The volume, rejection, and deployment diagnostics normally execute three queries in 18 node visits. Duplicate and regional diagnostics normally execute one query in eight visits.

 Evidence supplied to the reasoner is limited to five sample rows per evidence item and includes the executed SQL and returned row count. Samples are explicitly identified as samples. Aggregate queries are used when population-level counts are required.

 Errors and truncation prevent a result from being marked completed. Incomplete results have overall confidence set to zero while retaining the available evidence. A wall-clock deadline or cancellation stops execution without making another model call.

 Workflow state is process-local. The service runs with one worker, supports four active investigations, retains up to 100 terminal runs, and expires terminal runs after one hour by default.

 ## Result contract

 Python and the Java frontend-facing API expose `summary`, `findings`, `probableRootCause`, `confidence`, `evidence`, `toolExecutions`, and `sqlQueries`, together with investigation identity, status, and timestamps.

 Findings contain:

 - `id`
- `title`
- `description`
- `confidence` (0–1)
- `evidenceIds`

 Evidence contains:

 - `id`
- `type: sql_result`
- `description`
- `query`
- `rowCount`
- `sqlQueryId`
- `columns`
- `rows`

 Numeric confidence is an uncalibrated assessment and should not be interpreted as a statistical probability.

 Complete sanitized tool-attempt records are written to structured logs. Public tool execution summaries retain the established API shape. See guardrails.

 ## Deterministic development scenarios

 Development mode does not require a model API key. Queries execute against the committed synthetic fixture, and calculations use the returned SQL results rather than hard-coded answer values.

 The deterministic scenarios use fixed demonstration windows and identify those periods explicitly; they are not interpreted as the current week or current business data.

 | Question family | Fixed UTC window | Evidence |
| --- | --- | --- |
| Transaction volume decline | June 8–14 vs June 15–21, 2026 | 1,400 → 700 transactions; rejections 14 → 714; preceding release |
| Rejected records spike | Same weeks | Rejections 14 → 714 with the corresponding volume comparison |
| Duplicate transactions | June 24–26, 2026 | 60 business-key groups, 120 participating rows, 60 excess rows |
| Regional abnormal behavior | June 29–July 5 vs July 6–12, 2026 | East declined status 14/350 → 280/350; other regions remain 14/350 |
| Deployment and pipeline incident | June 14–21, 2026 | Release precedes the elevated-rejection window; temporal association does not establish causation |

Duplicate matching excludes surrogate ID and `created_at`. Matching attributes identify candidate replays but do not establish duplicate identity without an upstream event ID.

 Regional declined transaction status is distinct from ingestion rejection.

 Unsupported development questions return insufficient evidence rather than fabricated findings. Model-backed investigations receive an explicit UTC as-of time and must determine the available data coverage before selecting a comparison period.

 ## Verification

 Tests assert SQL outcomes, evidence references, workflow state transitions, execution budgets, and API contracts rather than relying on exact generated wording.

 A structured-model integration test exercises the real `ModelReasoner` call sequence using returned fixture evidence. Live PostgreSQL and paid-provider execution remain unverified; deterministic and mocked-model tests do not substitute for those environments.
