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
    loaded_at TIMESTAMP
);
