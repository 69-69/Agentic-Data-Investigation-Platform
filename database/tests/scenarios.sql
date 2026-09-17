-- Read-only examples. All time boundaries are UTC.
-- 1. Weekly volume: 1400, then 700 (50% decline).
SELECT date_trunc('week', transaction_date AT TIME ZONE 'UTC')::date AS week,
       count(*) AS ingested_transactions
FROM analytics.transactions
WHERE transaction_date >= TIMESTAMPTZ '2026-06-08 00:00:00+00'
  AND transaction_date < TIMESTAMPTZ '2026-06-22 00:00:00+00'
GROUP BY 1 ORDER BY 1;

-- 2. Seven runs: processed 100 / rejected 102 each; normal rejection count is 2.
SELECT started_at, records_processed, records_rejected, error_code
FROM analytics.pipeline_runs WHERE records_rejected > 2 ORDER BY started_at;

-- 3. 20 excess rows/day on June 24–26, 60 total. IDs/ingestion times differ.
WITH duplicates AS (
  SELECT customer_id, transaction_date, amount, transaction_type, channel,
         merchant_category, region, status, count(*) - 1 AS excess_rows
  FROM analytics.transactions
  GROUP BY customer_id, transaction_date, amount, transaction_type, channel,
           merchant_category, region, status
  HAVING count(*) > 1
)
SELECT (transaction_date AT TIME ZONE 'UTC')::date AS day,
       count(*) AS duplicate_groups, sum(excess_rows) AS excess_rows
FROM duplicates GROUP BY 1 ORDER BY 1;

-- 4. East changes from 4% to 80% declined; other regions stay at 4%.
SELECT date_trunc('week', transaction_date AT TIME ZONE 'UTC')::date AS week,
       region, count(*) AS total,
       count(*) FILTER (WHERE status = 'declined') AS declined,
       round(100.0 * count(*) FILTER (WHERE status = 'declined') / count(*), 2) AS declined_pct
FROM analytics.transactions
WHERE transaction_date >= TIMESTAMPTZ '2026-06-29 00:00:00+00'
  AND transaction_date < TIMESTAMPTZ '2026-07-13 00:00:00+00'
GROUP BY 1, 2 ORDER BY 1, 2;

-- 5. 20 missing categories (July 15–16); 10 malformed channels (July 17).
SELECT (transaction_date AT TIME ZONE 'UTC')::date AS day,
       count(*) FILTER (WHERE merchant_category IS NULL) AS missing_categories,
       count(*) FILTER (WHERE channel NOT IN ('web', 'mobile', 'branch')) AS malformed_channels
FROM analytics.transactions
WHERE merchant_category IS NULL OR channel NOT IN ('web', 'mobile', 'branch')
GROUP BY 1 ORDER BY 1;

-- 6. Release 2.4.0 precedes the affected week by 15 minutes; 7 elevated runs / 714 rejections.
-- Temporal association is evidence for a hypothesis, not proof of causation.
SELECT d.service_name, d.version, d.deployed_at,
       TIMESTAMPTZ '2026-06-15 00:00:00+00' - d.deployed_at AS lead_to_affected_week,
       count(*) AS elevated_runs, sum(p.records_rejected) AS rejected
FROM analytics.deployments d
JOIN analytics.pipeline_runs p ON p.pipeline_name = d.service_name
 AND p.started_at >= d.deployed_at AND p.started_at < d.deployed_at + INTERVAL '8 days'
WHERE d.version = '2.4.0' AND p.records_rejected > 2
GROUP BY d.service_name, d.version, d.deployed_at;
