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

CREATE TABLE IF NOT EXISTS etl.current_state (
    state_id BIGINT,
    entity_type VARCHAR,
    cycle INTEGER,
    table_name VARCHAR,
    entity_name VARCHAR,
    last_operation VARCHAR,
    operation_status VARCHAR,
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
