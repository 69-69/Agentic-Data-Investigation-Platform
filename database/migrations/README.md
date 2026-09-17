# Migrations

 Run `apply.sql` with PostgreSQL 17 `psql` as the bootstrap administrator. It applies numbered migrations once using an explicit ledger, transaction, and advisory lock. `\ir` resolves includes relative to each script, so the same scripts work from both host and container paths.

 Applied migrations are immutable. Add a new numbered migration file and a corresponding guarded ledger entry in `apply.sql`. This small runner does not checksum existing migrations or provide down migrations.

 Migration 002 creates a cluster-wide `investigation_reader` `NOLOGIN` role. Use a dedicated local cluster/database. If a role with that name already exists, migration 002 fails rather than silently reusing potentially privileged access.

 Administrator privileges are required to create roles.

 The reader has `SELECT` access to five explicitly listed analytical tables, no access to the migration ledger, no `CREATE` privilege on the schema, no database `TEMP` privilege, and no credentials. Enabling login is deferred to private runtime provisioning.

 Default read-only and timeout settings apply when the role logs in; they do not apply automatically when using `SET ROLE`. Future tools must still set transaction controls explicitly.

 `PUBLIC` function privileges and PostgreSQL builtins do not provide a complete safe-function boundary. The SQL guard is therefore mandatory before exposing generated SQL.

 New tables do not receive reader access automatically.
