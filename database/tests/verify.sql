\set ON_ERROR_STOP on
BEGIN;
SET LOCAL TIME ZONE 'UTC';
DO $$
DECLARE n bigint; relation text;
BEGIN
  IF (SELECT count(*) FROM analytics.customers) <> 400
    OR (SELECT count(*) FROM analytics.transactions) <> 10560
    OR (SELECT count(*) FROM analytics.pipeline_runs) <> 56
    OR (SELECT count(*) FROM analytics.data_quality_events) <> 4
    OR (SELECT count(*) FROM analytics.deployments) <> 3 THEN
    RAISE EXCEPTION 'Fixture row counts differ';
  END IF;
  IF (SELECT count(*) FROM analytics.transactions WHERE transaction_date >= TIMESTAMPTZ '2026-06-08 00:00:00+00' AND transaction_date < TIMESTAMPTZ '2026-06-15 00:00:00+00') <> 1400
    OR (SELECT count(*) FROM analytics.transactions WHERE transaction_date >= TIMESTAMPTZ '2026-06-15 00:00:00+00' AND transaction_date < TIMESTAMPTZ '2026-06-22 00:00:00+00') <> 700 THEN
    RAISE EXCEPTION 'Weekly volume scenario differs';
  END IF;
  IF (SELECT count(*) FROM analytics.pipeline_runs WHERE records_rejected = 102 AND records_processed = 100
      AND started_at >= TIMESTAMPTZ '2026-06-15 00:00:00+00' AND started_at < TIMESTAMPTZ '2026-06-22 00:00:00+00') <> 7 THEN
    RAISE EXCEPTION 'Pipeline rejection scenario differs';
  END IF;
  IF EXISTS (
    SELECT 1 FROM analytics.pipeline_runs p
    WHERE p.records_processed <> (SELECT count(*) FROM analytics.transactions t
      WHERE t.transaction_date::date = p.started_at::date)
  ) THEN RAISE EXCEPTION 'Pipeline accepted counts do not reconcile'; END IF;
  SELECT sum(c - 1) INTO n FROM (
    SELECT count(*) c FROM analytics.transactions
    GROUP BY customer_id, transaction_date, amount, transaction_type, channel, merchant_category, region, status
    HAVING count(*) > 1
  ) d;
  IF n IS DISTINCT FROM 60 THEN RAISE EXCEPTION 'Duplicate scenario differs'; END IF;
  IF (SELECT count(*) FROM analytics.transactions WHERE region = 'east' AND status = 'declined'
      AND transaction_date >= TIMESTAMPTZ '2026-07-06 00:00:00+00' AND transaction_date < TIMESTAMPTZ '2026-07-13 00:00:00+00') <> 280
    OR (SELECT count(*) FROM analytics.transactions WHERE region = 'east' AND status = 'declined'
      AND transaction_date >= TIMESTAMPTZ '2026-06-29 00:00:00+00' AND transaction_date < TIMESTAMPTZ '2026-07-06 00:00:00+00') <> 14 THEN
    RAISE EXCEPTION 'Regional anomaly differs';
  END IF;
  IF (SELECT count(*) FROM analytics.transactions WHERE merchant_category IS NULL) <> 20
    OR (SELECT count(*) FROM analytics.transactions WHERE channel NOT IN ('web','mobile','branch')) <> 10 THEN
    RAISE EXCEPTION 'Data quality scenario differs';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM analytics.deployments WHERE service_name = 'transaction_ingestion'
    AND version = '2.4.0' AND deployed_at = TIMESTAMPTZ '2026-06-14 23:45:00+00') THEN
    RAISE EXCEPTION 'Deployment scenario differs';
  END IF;
  FOREACH relation IN ARRAY ARRAY['analytics.customers','analytics.transactions','analytics.pipeline_runs',
                                  'analytics.data_quality_events','analytics.deployments'] LOOP
    IF NOT has_table_privilege('investigation_reader', relation, 'SELECT')
      OR has_table_privilege('investigation_reader', relation, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') THEN
      RAISE EXCEPTION 'Unexpected table privileges: %', relation;
    END IF;
  END LOOP;
  IF has_schema_privilege('investigation_reader', 'analytics', 'CREATE')
    OR has_schema_privilege('investigation_reader', 'public', 'CREATE')
    OR has_database_privilege('investigation_reader', current_database(), 'TEMP,CREATE')
    OR has_schema_privilege('investigation_reader', 'platform', 'USAGE') THEN
    RAISE EXCEPTION 'Reader has excessive schema/database access';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'investigation_reader'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolcanlogin)) THEN
    RAISE EXCEPTION 'Reader attributes differ';
  END IF;
END $$;
-- Exercise actual constraints; successful writes raise our uncaught exception.
DO $$ BEGIN
  BEGIN
    INSERT INTO analytics.transactions VALUES (999999, 999999, now(), 1, 'purchase', 'web', 'retail', 'east', 'settled', now());
    RAISE EXCEPTION 'Foreign key was not enforced';
  EXCEPTION WHEN foreign_key_violation THEN NULL; END;
  BEGIN
    INSERT INTO analytics.transactions VALUES (999999, 1, now(), -1, 'purchase', 'web', 'retail', 'east', 'settled', now());
    RAISE EXCEPTION 'Positive amount constraint was not enforced';
  EXCEPTION WHEN check_violation THEN NULL; END;
END $$;
SET LOCAL ROLE investigation_reader;
SELECT count(*) AS reader_visible_transactions FROM analytics.transactions;
DO $$ BEGIN
  BEGIN
    INSERT INTO analytics.customers VALUES (999999, 'retail', 'east', now());
    RAISE EXCEPTION 'Reader INSERT unexpectedly succeeded';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    DELETE FROM analytics.transactions WHERE id = -1;
    RAISE EXCEPTION 'Reader DELETE unexpectedly succeeded';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    CREATE TABLE analytics.reader_must_not_create (id integer);
    RAISE EXCEPTION 'Reader CREATE unexpectedly succeeded';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
\echo 'PASS: fixture scenarios, constraints and reader permissions'
