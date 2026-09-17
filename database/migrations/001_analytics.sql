CREATE SCHEMA analytics;
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;

CREATE TABLE analytics.customers (
    id bigint PRIMARY KEY CHECK (id > 0),
    customer_segment text NOT NULL CHECK (customer_segment IN ('retail', 'premium', 'small_business')),
    region text NOT NULL CHECK (region IN ('north', 'south', 'east', 'west')),
    created_at timestamptz NOT NULL
);
CREATE TABLE analytics.transactions (
    id bigint PRIMARY KEY CHECK (id > 0),
    customer_id bigint NOT NULL REFERENCES analytics.customers(id),
    transaction_date timestamptz NOT NULL,
    amount numeric(12,2) NOT NULL CHECK (amount > 0 AND amount <> 'NaN'::numeric),
    transaction_type text NOT NULL CHECK (transaction_type IN ('purchase', 'refund', 'transfer')),
    channel text NOT NULL CHECK (length(channel) BETWEEN 1 AND 40),
    merchant_category text CHECK (length(merchant_category) BETWEEN 1 AND 80),
    region text NOT NULL CHECK (region IN ('north', 'south', 'east', 'west')),
    status text NOT NULL CHECK (status IN ('settled', 'declined')),
    created_at timestamptz NOT NULL CHECK (created_at >= transaction_date)
);
COMMENT ON TABLE analytics.transactions IS 'Completely synthetic ingestion records; distinct IDs may represent a replayed business event.';
COMMENT ON COLUMN analytics.transactions.amount IS 'Positive magnitude in synthetic USD; transaction_type supplies direction.';
COMMENT ON COLUMN analytics.transactions.channel IS 'Raw source channel: expected web/mobile/branch; malformed source text intentionally retained for investigation.';
COMMENT ON COLUMN analytics.transactions.merchant_category IS 'Nullable source attribute; missing categories are intentionally retained as data-quality evidence.';
COMMENT ON COLUMN analytics.transactions.transaction_date IS 'Business event time; all fixture timestamps are explicit UTC.';

CREATE TABLE analytics.pipeline_runs (
    id bigint PRIMARY KEY CHECK (id > 0),
    pipeline_name text NOT NULL CHECK (length(pipeline_name) BETWEEN 1 AND 100),
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL CHECK (completed_at >= started_at),
    records_processed integer NOT NULL CHECK (records_processed >= 0),
    records_rejected integer NOT NULL CHECK (records_rejected >= 0),
    status text NOT NULL CHECK (status IN ('completed', 'partial', 'failed')),
    error_code text,
    error_message text,
    CHECK ((error_code IS NULL) = (error_message IS NULL))
);
COMMENT ON COLUMN analytics.pipeline_runs.records_processed IS 'Accepted ingestion rows, including replay duplicates; total input is processed plus rejected.';
COMMENT ON TABLE analytics.pipeline_runs IS 'Daily runs cover the UTC calendar date of started_at; time-window association only, no row-level run lineage.';

CREATE TABLE analytics.data_quality_events (
    id bigint PRIMARY KEY CHECK (id > 0),
    detected_at timestamptz NOT NULL,
    dataset_name text NOT NULL CHECK (length(dataset_name) BETWEEN 1 AND 100),
    issue_type text NOT NULL CHECK (length(issue_type) BETWEEN 1 AND 80),
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    affected_records integer NOT NULL CHECK (affected_records > 0),
    description text NOT NULL CHECK (length(description) BETWEEN 1 AND 1000)
);
CREATE TABLE analytics.deployments (
    id bigint PRIMARY KEY CHECK (id > 0),
    service_name text NOT NULL CHECK (length(service_name) BETWEEN 1 AND 100),
    version text NOT NULL CHECK (length(version) BETWEEN 1 AND 60),
    deployed_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('succeeded', 'failed', 'rolled_back')),
    UNIQUE (service_name, version, deployed_at)
);
CREATE INDEX transactions_date_idx ON analytics.transactions(transaction_date);
CREATE INDEX transactions_region_date_idx ON analytics.transactions(region, transaction_date);
CREATE INDEX transactions_customer_date_idx ON analytics.transactions(customer_id, transaction_date);
CREATE INDEX pipeline_runs_name_started_idx ON analytics.pipeline_runs(pipeline_name, started_at);
CREATE INDEX data_quality_dataset_detected_idx ON analytics.data_quality_events(dataset_name, detected_at);
CREATE INDEX deployments_service_date_idx ON analytics.deployments(service_name, deployed_at);
