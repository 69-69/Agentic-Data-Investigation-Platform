-- Dedicated local database only. Do not reuse an existing global role silently.
CREATE ROLE investigation_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO investigation_reader', current_database()) \gexec
GRANT USAGE ON SCHEMA analytics TO investigation_reader;
GRANT SELECT ON analytics.customers, analytics.transactions, analytics.pipeline_runs,
    analytics.data_quality_events, analytics.deployments TO investigation_reader;
ALTER ROLE investigation_reader SET default_transaction_read_only = on;
ALTER ROLE investigation_reader SET statement_timeout = '5s';
ALTER ROLE investigation_reader SET lock_timeout = '1s';
ALTER ROLE investigation_reader SET search_path = pg_catalog, analytics;
-- No blanket future-table/default SELECT grants: each new relation needs review.
-- NOLOGIN deliberately avoids creating credentials; future private provisioning
-- will enable the runtime login. SQL validation/function policy is still required.
