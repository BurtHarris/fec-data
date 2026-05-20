-- Cycle-aware snapshot table for candidate master (cn) extracts.
-- This table supports cycle-level baselines and quick comparisons.

CREATE TABLE IF NOT EXISTS fec_cn_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
