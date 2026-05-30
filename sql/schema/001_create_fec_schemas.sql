CREATE SCHEMA IF NOT EXISTS raw_fec;
CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS review;

CREATE TABLE IF NOT EXISTS etl.load_history (
    load_id BIGINT,
    cycle INTEGER,
    table_name VARCHAR,
    source_zip_path VARCHAR,
    source_entry_name VARCHAR,
    source_file_hash VARCHAR,
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

-- Durable human review notes. Unlike etl.qa_issue_log, these tables are not
-- only run output; they are a project memory for investigated oddities.
CREATE TABLE IF NOT EXISTS review.issue (
    issue_id BIGINT,
    issue_key VARCHAR,
    title VARCHAR,
    issue_type VARCHAR,
    issue_subtype VARCHAR,
    severity VARCHAR,
    status VARCHAR,
    confidence VARCHAR,
    cycle INTEGER,
    source_schema VARCHAR,
    source_table VARCHAR,
    source_column VARCHAR,
    detection_method VARCHAR,
    detection_name VARCHAR,
    detected_row_count BIGINT,
    detected_amount DECIMAL(18,2),
    summary VARCHAR,
    current_explanation VARCHAR,
    accepted_reason VARCHAR,
    opened_by VARCHAR,
    opened_at TIMESTAMP,
    updated_at TIMESTAMP,
    accepted_by VARCHAR,
    accepted_at TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review.issue_relationship (
    relationship_id BIGINT,
    from_issue_id BIGINT,
    to_issue_id BIGINT,
    relationship_type VARCHAR,
    relationship_note VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review.issue_entity (
    issue_entity_id BIGINT,
    issue_id BIGINT,
    entity_type VARCHAR,
    entity_id VARCHAR,
    entity_label VARCHAR,
    role VARCHAR,
    source_table VARCHAR,
    source_column VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS review.issue_evidence (
    evidence_id BIGINT,
    issue_id BIGINT,
    evidence_type VARCHAR,
    source_label VARCHAR,
    source_url VARCHAR,
    evidence_text VARCHAR,
    query_text VARCHAR,
    observed_value VARCHAR,
    observed_at TIMESTAMP,
    added_by VARCHAR
);

CREATE TABLE IF NOT EXISTS review.issue_decision (
    decision_id BIGINT,
    issue_id BIGINT,
    decision VARCHAR,
    decision_reason VARCHAR,
    decided_by VARCHAR,
    decided_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review.issue_metric (
    issue_metric_id BIGINT,
    issue_id BIGINT,
    metric_name VARCHAR,
    metric_value DOUBLE,
    metric_unit VARCHAR,
    measured_at TIMESTAMP,
    query_text VARCHAR
);
