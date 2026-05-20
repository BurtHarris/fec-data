-- Cycle-aware snapshot table for PAS2 extracts.

CREATE TABLE IF NOT EXISTS fec_pas2_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
