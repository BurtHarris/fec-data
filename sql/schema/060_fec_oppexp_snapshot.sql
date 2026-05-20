-- Cycle-aware snapshot table for operating expenditures (oppexp) extracts.

CREATE TABLE IF NOT EXISTS fec_oppexp_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
