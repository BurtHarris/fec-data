-- Cycle-aware snapshot table for candidate-committee linkage (ccl) extracts.

CREATE TABLE IF NOT EXISTS fec_ccl_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
