\set ON_ERROR_STOP on
BEGIN;
-- Shared lock with seeding prevents concurrent bootstrap races.
SELECT pg_advisory_xact_lock(782341, 1);
CREATE SCHEMA IF NOT EXISTS platform;
REVOKE ALL ON SCHEMA platform FROM PUBLIC;
CREATE TABLE IF NOT EXISTS platform.schema_migrations (
    version integer PRIMARY KEY,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
SELECT NOT EXISTS (SELECT 1 FROM platform.schema_migrations WHERE version = 1) AS apply_v1 \gset
\if :apply_v1
\ir 001_analytics.sql
INSERT INTO platform.schema_migrations VALUES (1, 'Analytical schema and indexes', now());
\endif
SELECT NOT EXISTS (SELECT 1 FROM platform.schema_migrations WHERE version = 2) AS apply_v2 \gset
\if :apply_v2
\ir 002_reader.sql
INSERT INTO platform.schema_migrations VALUES (2, 'Restricted reader identity', now());
\endif
COMMIT;
