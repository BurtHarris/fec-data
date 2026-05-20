-- Cycle-aware snapshot table for weball extracts.

CREATE TABLE IF NOT EXISTS fec_weball_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
