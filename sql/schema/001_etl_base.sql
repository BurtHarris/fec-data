-- Base ETL control tables for DuckDB loads.

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id BIGINT,
    run_started_at TIMESTAMP,
    phase VARCHAR,
    status VARCHAR,
    details VARCHAR
);

CREATE TABLE IF NOT EXISTS etl_cycle_artifacts (
    cycle INTEGER,
    zone VARCHAR,
    file_name VARCHAR,
    file_size_bytes BIGINT,
    discovered_at TIMESTAMP
);
