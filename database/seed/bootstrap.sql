\set ON_ERROR_STOP on
\ir ../migrations/apply.sql
\ir load.sql
\ir ../tests/verify.sql
