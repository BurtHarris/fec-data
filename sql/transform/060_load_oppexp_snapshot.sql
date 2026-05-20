-- Baseline snapshot for oppexp using raw zip files.
-- Row-level counting is deferred until extraction/loading for this family is enabled.

CREATE OR REPLACE TEMP TABLE _oppexp_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(file, chr(92), '/'), 'data/([0-9]{4})/raw/oppexp[0-9]{2}\.zip$', 1), '') AS INTEGER) AS cycle,
    CAST(NULL AS BIGINT) AS row_count,
    min(replace(file, chr(92), '/')) AS source_path,
    now() AS loaded_at
FROM glob('data/*/raw/oppexp*.zip')
GROUP BY 1;

DELETE FROM fec_oppexp_snapshot
WHERE cycle IN (SELECT cycle FROM _oppexp_counts);

INSERT INTO fec_oppexp_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _oppexp_counts
WHERE cycle IS NOT NULL;
