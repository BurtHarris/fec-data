CREATE SCHEMA IF NOT EXISTS raw_fec;
CREATE SCHEMA IF NOT EXISTS etl;

CREATE TABLE IF NOT EXISTS etl.load_history (
    load_id BIGINT,
    cycle INTEGER,
    table_name VARCHAR,
    source_zip_path VARCHAR,
    source_entry_name VARCHAR,
    target_table_name VARCHAR,
    row_count BIGINT,
    duration_ms BIGINT,
    loaded_at TIMESTAMP
);

ALTER TABLE etl.load_history ADD COLUMN IF NOT EXISTS duration_ms BIGINT;

CREATE TABLE IF NOT EXISTS etl.fetch_history (
    fetch_id BIGINT,
    cycle INTEGER,
    table_name VARCHAR,
    zip_name VARCHAR,
    source_url VARCHAR,
    fetch_status VARCHAR,
    http_status INTEGER,
    content_length BIGINT,
    response_date VARCHAR,
    last_modified VARCHAR,
    etag VARCHAR,
    local_file_size BIGINT,
    fetched_at TIMESTAMP,
    error_text VARCHAR
);

CREATE TABLE IF NOT EXISTS etl.qa_issue_log (
    issue_id BIGINT,
    run_id BIGINT,
    cycle INTEGER,
    table_name VARCHAR,
    issue_type VARCHAR,
    severity VARCHAR,
    issue_key VARCHAR,
    issue_count BIGINT,
    issue_details VARCHAR,
    detected_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl.qa_run_summary (
    run_id BIGINT,
    cycle INTEGER,
    table_name VARCHAR,
    metric_name VARCHAR,
    metric_value DOUBLE,
    status VARCHAR,
    computed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl.current_state (
    state_id BIGINT,
    entity_type VARCHAR,
    cycle INTEGER,
    table_name VARCHAR,
    entity_name VARCHAR,
    last_operation VARCHAR,
    operation_status VARCHAR,
    quality_status VARCHAR,
    source_url VARCHAR,
    source_zip_path VARCHAR,
    source_entry_name VARCHAR,
    target_table_name VARCHAR,
    http_status INTEGER,
    content_length BIGINT,
    row_count BIGINT,
    duration_ms BIGINT,
    response_date VARCHAR,
    last_modified VARCHAR,
    etag VARCHAR,
    error_text VARCHAR,
    updated_at TIMESTAMP
);

ALTER TABLE etl.current_state ADD COLUMN IF NOT EXISTS quality_status VARCHAR;
