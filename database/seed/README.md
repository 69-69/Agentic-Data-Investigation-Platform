# Synthetic Fixture Loading

 `synthetic-v1.sql` is a committed COPY-data fixture that allows PostgreSQL to initialize without Python installed in the database image. Regenerate it with:

```
python3 database/synthetic-data/generate.py
```

 Run the command from the repository root. The generator uses only Python's standard library and does not connect to a database.

 `load.sql` inserts the fixture and its version ledger atomically, once. Re-running it skips an already loaded version; it does not overwrite existing edits or duplicate records. An unversioned database with conflicting IDs fails and rolls back.

 Regeneration changes the fixture files only; it does not modify the live database.

 For an intentional fixture revision, create a new dataset version with a corresponding migration/load plan, or use a separate disposable database. There is no automatic truncate or reset.

 `bootstrap.sql` applies migrations, loads the fixture, and runs assertions. Docker runs it automatically only when initializing an empty volume.

 For existing installations, run it explicitly as documented in the root README. If initialization fails, fix the underlying cause and run the bootstrap again. Restarting a partially initialized Docker volume does not rerun the Docker initialization scripts.

 Migrations and seeding commit separately, so a seed failure leaves the schema available for repair.
