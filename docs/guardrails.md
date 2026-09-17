# SQL and Tool Security Contract

 The application uses a conservative structural SQL guard, explicit database tools, and bounded execution.

 The SQLite development adapter has real SQL and security tests. The PostgreSQL adapter validates roles and schema access and applies read-only and timeout controls, but live PostgreSQL verification remains outstanding; its database-control tests use driver mocks.

 Migration 002 creates the `NOLOGIN` `investigation_reader` role. Private runtime login provisioning is documented separately.

 This document describes the implemented security boundary and does not constitute a production security certification.

 ## Structural Validation and Fail-Closed Behavior

 The SQL guard permits exactly one PostgreSQL statement whose effective operation is `SELECT` or a safe `WITH ... SELECT`.

 The entire input is parsed with a PostgreSQL-aware structural parser. Unsupported or unknown AST nodes are rejected. Keyword or prefix checks are not used as the security boundary.

 Validation traverses nested queries and CTEs and checks:

 - Aliases and CTE names
- Referenced relations
- Functions
- Operators
- Casts
- Query structure and scope

 SQLGlot PostgreSQL tokenization rejects line and block comments, including nested and empty comments. Comment-like text inside quoted string literals remains data. Rejected comments are not stripped and then executed.

 The guard rejects:

 - Parse errors
- Stacked statements
- Data-modifying CTEs
- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `TRUNCATE`
- `CREATE`
- `REPLACE`
- `MERGE`
- `CALL`
- `EXECUTE`
- `COPY`
- `GRANT`
- `REVOKE`
- `COMMENT`
- `VACUUM`
- `ANALYZE`
- `REFRESH`
- `LOCK`
- `SET`
- `RESET`
- `DO`
- `SELECT INTO`
- Row locking such as `FOR UPDATE` and `FOR SHARE`
- `EXPLAIN`
- Recursive CTEs
- Other unsupported database-specific constructs

 A read-only-looking statement can still have side effects. Unapproved functions are therefore denied, including user-defined functions, `SECURITY DEFINER` functions, sequence mutation, advisory locks, sleep functions, filesystem access, external/network extensions, and dynamic SQL.

 The function, operator, and type policies are explicit. Volatility metadata alone is not treated as a sufficient safety boundary.

 Approved views and their dependencies must also be reviewed to prevent indirect access to forbidden relations or functions.

 Examples that must be rejected:

```
SELECT * FROM analytics.transactions; DROP TABLE analytics.transactions;
```

```
WITH removed AS (
    DELETE FROM analytics.transactions RETURNING *
)
SELECT * FROM removed;
```

```
SELECT pg_sleep(60);
```

```
SELECT * INTO copied FROM analytics.transactions;
```

 These cases are covered by the guard's rejection tests.

 ## Allowlist and Resource Controls

 `SQL_ALLOWED_TABLES` is an application-owned list of schema-qualified relations. PostgreSQL mode rejects an empty allowlist.

 Every referenced relation, including relations inside subqueries and CTEs, is resolved against the allowlist.

 Generated SQL uses explicit approved schemas. The guard rejects:

 - System catalogs
- `information_schema`
- Temporary schemas
- Foreign tables
- Unapproved relations

 The `get_database_schema` tool uses trusted metadata queries internally and returns only approved table and column names. It does not expose credentials or unrestricted catalog contents.

 Result limits are configured with:

```
SQL_DEFAULT_ROW_LIMIT=100
SQL_MAX_ROW_LIMIT=500
```

 Configuration must satisfy:

```
1 ≤ default limit ≤ maximum limit
```

 The application applies an AST-safe outer result cap when a query has no limit or requests more than the permitted maximum. The cap is applied without changing the inputs to aggregate operations.

 The executor fetches at most `cap + 1` rows so it can detect truncation, returns at most `cap` rows, and records the actual executed SQL.

 Result bytes and individual cell sizes are also bounded:

 - 32,000 bytes per query
- 16 KiB per string value

 Truncation is reported explicitly.

 Row limits constrain returned data but do not by themselves constrain database computation.

 ## Execution Controls

 Every SQL execution uses trusted application configuration for:

 - Server-side statement timeout
- Read-only transaction mode
- Lock timeout
- Connection acquisition/client timeout
- Overall investigation deadline

 The default statement timeout is:

```
SQL_STATEMENT_TIMEOUT_MS=5000
```

 Model-generated settings cannot override these values.

 Failures are rolled back and connection state is reset before reuse. The PostgreSQL adapter closes connections rather than retaining a pool.

 Validation is repeated at the execution boundary. A caller cannot bypass the policy by substituting SQL after validation.

 The SQLite adapter additionally uses `query_only`, an authorizer, and a progress timeout.

 ## Database Defense in Depth

 The database uses a dedicated non-owner reader with only the privileges required to access approved analytical data.

 The reader must not have:

 - Superuser access
- Role or database creation privileges
- `BYPASSRLS`
- Privileged role memberships
- Migration credentials
- Access to migration metadata

 The database configuration restricts schema and database privileges as required, including schema `CREATE`, database `TEMP`, and unsafe function `EXECUTE`.

 Migrations and seed operations use separate privileged configuration and are not available to the agent.

 Read-only database permissions limit the impact of application validation mistakes. Structural validation provides an additional boundary against data exfiltration, unsafe functions, and resource abuse that database permissions alone cannot prevent.

 Neither layer replaces the other.

 Real PostgreSQL testing must verify effective permissions, inherited privileges, view and function behavior, and connection-level controls.

 ## Credential and Model Boundaries

 The agent exposes only these database tools:

 - `get_database_schema`
- `get_table_metadata`
- `validate_sql`
- `execute_read_only_sql`
- `get_basic_statistics`

 The model proposes SQL through structured output. It does not receive a database adapter or connection.

 Tool arguments are typed and size-bounded. Tools do not accept hostnames, DSNs, credentials, or arbitrary connection options from the model.

 Database connectivity belongs exclusively to the tool layer.

 The model has no access to:

 - Shell commands
- Python execution
- Filesystem access
- Arbitrary HTTP requests
- Unrestricted database execution

 Credentials are stored in private runtime configuration. They are never serialized into prompts, tool schemas, graph checkpoints, frontend responses, or logs.

 Questions, generated SQL, tool arguments, and database text are treated as untrusted data. Instructions embedded in database rows cannot change security policy, grant permissions, or invoke additional capabilities.

 Only the minimum required data should be sent to the model provider. Provider data-handling requirements must be reviewed before using non-synthetic data.

 ## Audit and Evidence

 Every tool attempt records a bounded structured audit event containing:

 - Timestamp
- Investigation ID
- Correlation ID
- Tool name
- Duration
- Validation decision
- Policy reason
- Row count
- Success or failure

 SQL audit metadata uses sanitized SQL and a query hash. Literals, comments, connection strings, and result rows are not written to logs.

 The exact executed SQL and safe parameters are retained separately as access-controlled evidence. If that evidence contains restricted data, the public representation must be redacted explicitly and must not be presented as executable SQL.

 Successful synthetic-data queries expose their executed SQL as evidence.

 Rejected SQL is labeled as rejected and is never presented as executed evidence.

 Audit retention and access controls must be defined before deployment.

 ## Required Security Tests

 The test suite covers or should cover:

 - Safe SELECT statements
- Safe CTEs
- Nested mutations
- Stacked statements
- SQL comments and quoting tricks
- Aliases and nested scopes
- Forbidden relations
- Forbidden views and functions
- `SELECT INTO`
- Row locking
- Result-limit bypasses
- Parameter binding
- Cancellation
- Error handling
- Credential redaction

 Integration testing against PostgreSQL must verify:

 - Effective reader permissions
- Inherited privileges
- Read-only transactions
- Server-side timeouts
- Query cancellation
- Rollback and connection cleanup
- Result truncation
- Function and view behavior
- Credential isolation

 Guard and resource-budget decisions remain authoritative regardless of instructions supplied by a model or user.

 ## Implemented Security Boundary

 The guard uses SQLGlot 30.18.0 with PostgreSQL dialect tokenization, AST validation, and scope resolution.

 The accepted SQL subset includes:

 - `SELECT`
- Nonrecursive CTEs
- `UNION`
- Simple joins
- Comparisons
- Arithmetic
- `CASE`
- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`

 Casts, custom functions, window functions, system relations, locks, and unsupported AST nodes are denied.

 Only schema-qualified, approved base tables are accepted by generated SQL.

 The PostgreSQL adapter additionally rejects views, foreign tables, custom column types, ownership/privilege escalation, and unsafe reader memberships.

 Runtime function resolution uses `pg_catalog` only, preventing model-selected aggregate names from resolving through the analytics schema.

 `LIMIT ALL` is normalized by the parser to an absent limit and is subsequently capped by the application-owned outer SELECT.

 The executor adds a safe outer bound and fetches at most one additional row for truncation detection. The exact executed SQL includes the applied bound.

 Data string literals are converted to named driver parameters after validation. PostgreSQL uses `%(p0)s`-style placeholders and SQLite uses `:p0` parameters.

 Numeric literals remain parser-rendered SQL so `ORDER BY` and `GROUP BY` ordinals retain their meaning.

 No raw user-derived text is concatenated into executable SQL. Identifiers cannot be value-bound and therefore require allowlisting and quoting.

 SQL evidence contains the validated bounded SQL with the original literals correctly quoted rather than the driver placeholder representation. This evidence is intended for the synthetic dataset and is not written to logs.

 The per-query data budget is 32,000 bytes. This is stricter than the result envelope used by the Java service and leaves room for accumulated evidence.

 ## Tool Implementation

 `agent-service/src/agent_service/tools/safe.py` provides the five asynchronous database-tool methods.

 The investigation graph uses this facade for schema inspection, validation, and execution.

 `get_table_metadata` returns the approved table name and columns.

 `get_basic_statistics` returns total, non-null, null, minimum, and maximum values. The aggregate queries support both text and numeric columns.

 Table and column names are validated against trusted metadata before identifiers are quoted. Unknown identifiers fail before candidate SQL execution.

 `guard.py` uses the pinned SQLGlot version with PostgreSQL dialect parsing, AST validation, and scope resolution. The supported SQL subset is intentionally narrower than the full PostgreSQL grammar.

 All SQL is validated again at the database execution boundary.

 Each facade attempt emits a JSON `guarded_tool_execution` record containing:

```
toolName
startTime
endTime
success
sanitizedArguments
rowCount
errorType
correlationId
```

 Non-query calls use a null row count. Failures and cancellations are recorded as well.

 SQL arguments are represented using SHA-256 hashes and shapes with literals and identifiers redacted. Metadata arguments use hashes.

 Raw exceptions, credentials, and result rows are excluded from logs.

 Unexpected adapter errors become `TOOL_FAILED`. Policy rejection becomes `SQL_REJECTED`. Cancellation is logged and re-raised.

 These audit records are written to the application log sink. No unbounded in-process audit history is retained.

 The public `toolExecutions` summaries retain the existing Java-compatible shape and field names.

 ## Verification Status

 The deterministic SQLite path has been exercised with real SQL and security tests.

 PostgreSQL control-path behavior is covered with driver mocks, including parameter binding and connection-control calls. Live PostgreSQL grant enforcement, timeout behavior, query cancellation, and dialect edge cases have not yet been verified against a running PostgreSQL instance.

 The PostgreSQL reader role and grants are defined in migration 002. No additional privileges or credentials are introduced by the tool layer.

 The current scope is synthetic data. Authentication, user-specific access controls, retention policy, and review of non-synthetic data disclosure remain required before public deployment.
