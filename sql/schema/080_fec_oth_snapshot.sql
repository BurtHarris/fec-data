-- Cycle-aware snapshot table for OTH extracts.

CREATE TABLE IF NOT EXISTS fec_oth_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
