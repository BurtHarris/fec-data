-- Cycle-aware snapshot table for individual contributions (indiv).
-- Large-table strategy: baseline from raw zip presence first; row counts can be
-- added in an incremental phase after staged parsing strategy is finalized.

CREATE TABLE IF NOT EXISTS fec_indiv_snapshot (
    cycle INTEGER,
    row_count BIGINT,
    source_path VARCHAR,
    load_mode VARCHAR,
    loaded_at TIMESTAMP,
    PRIMARY KEY (cycle)
);
