CREATE TABLE IF NOT EXISTS etl_load_history (
    load_id INTEGER,
    cycle INTEGER,
    table_name TEXT,
    source_zip_path TEXT,
    source_entry_name TEXT,
    source_file_hash TEXT,
    target_table_name TEXT,
    row_count INTEGER,
    duration_ms INTEGER,
    loaded_at TEXT
);

CREATE TABLE IF NOT EXISTS etl_fetch_history (
    fetch_id INTEGER,
    cycle INTEGER,
    table_name TEXT,
    zip_name TEXT,
    source_url TEXT,
    fetch_status TEXT,
    http_status INTEGER,
    content_length INTEGER,
    response_date TEXT,
    last_modified TEXT,
    etag TEXT,
    local_file_size INTEGER,
    fetched_at TEXT,
    error_text TEXT
);

CREATE TABLE IF NOT EXISTS etl_qa_issue_log (
    issue_id INTEGER,
    run_id INTEGER,
    cycle INTEGER,
    table_name TEXT,
    issue_type TEXT,
    severity TEXT,
    issue_key TEXT,
    issue_count INTEGER,
    issue_details TEXT,
    detected_at TEXT
);

CREATE TABLE IF NOT EXISTS etl_qa_run_summary (
    run_id INTEGER,
    cycle INTEGER,
    table_name TEXT,
    metric_name TEXT,
    metric_value REAL,
    status TEXT,
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS etl_current_state (
    state_id INTEGER,
    entity_type TEXT,
    cycle INTEGER,
    table_name TEXT,
    entity_name TEXT,
    last_operation TEXT,
    operation_status TEXT,
    quality_status TEXT,
    source_url TEXT,
    source_zip_path TEXT,
    source_entry_name TEXT,
    target_table_name TEXT,
    http_status INTEGER,
    content_length INTEGER,
    row_count INTEGER,
    duration_ms INTEGER,
    response_date TEXT,
    last_modified TEXT,
    etag TEXT,
    error_text TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS review_issue (
    issue_id INTEGER,
    issue_key TEXT,
    title TEXT,
    issue_type TEXT,
    issue_subtype TEXT,
    severity TEXT,
    status TEXT,
    confidence TEXT,
    cycle INTEGER,
    source_schema TEXT,
    source_table TEXT,
    source_column TEXT,
    detection_method TEXT,
    detection_name TEXT,
    detected_row_count INTEGER,
    detected_amount REAL,
    summary TEXT,
    current_explanation TEXT,
    accepted_reason TEXT,
    opened_by TEXT,
    opened_at TEXT,
    updated_at TEXT,
    accepted_by TEXT,
    accepted_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS review_issue_relationship (
    relationship_id INTEGER,
    from_issue_id INTEGER,
    to_issue_id INTEGER,
    relationship_type TEXT,
    relationship_note TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS review_issue_entity (
    issue_entity_id INTEGER,
    issue_id INTEGER,
    entity_type TEXT,
    entity_id TEXT,
    entity_label TEXT,
    role TEXT,
    source_table TEXT,
    source_column TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS review_issue_evidence (
    evidence_id INTEGER,
    issue_id INTEGER,
    evidence_type TEXT,
    source_label TEXT,
    source_url TEXT,
    evidence_text TEXT,
    query_text TEXT,
    observed_value TEXT,
    observed_at TEXT,
    added_by TEXT
);

CREATE TABLE IF NOT EXISTS review_issue_decision (
    decision_id INTEGER,
    issue_id INTEGER,
    decision TEXT,
    decision_reason TEXT,
    decided_by TEXT,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS review_issue_metric (
    issue_metric_id INTEGER,
    issue_id INTEGER,
    metric_name TEXT,
    metric_value REAL,
    metric_unit TEXT,
    measured_at TEXT,
    query_text TEXT
);
