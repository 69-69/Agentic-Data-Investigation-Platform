\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(782341, 1);
CREATE TABLE IF NOT EXISTS platform.seed_history (
    dataset_version text PRIMARY KEY,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
SELECT NOT EXISTS (SELECT 1 FROM platform.seed_history WHERE dataset_version = 'synthetic-v1') AS load_fixture \gset
\if :load_fixture
-- Fails on conflicting data; never truncate or silently overwrite existing work.
\ir synthetic-v1.sql
INSERT INTO platform.seed_history(dataset_version) VALUES ('synthetic-v1');
\endif
COMMIT;
ANALYZE analytics.customers;
ANALYZE analytics.transactions;
ANALYZE analytics.pipeline_runs;
ANALYZE analytics.data_quality_events;
ANALYZE analytics.deployments;
