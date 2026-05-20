-- Cycle-aware snapshot table for committee master (cm) extracts.
-- This keeps a lightweight baseline for cross-cycle comparisons.

CREATE TABLE IF NOT EXISTS fec_cm_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
