-- Baseline snapshot for oth using raw zip files.
-- Row-level counting is deferred until extraction/loading for this family is enabled.

CREATE OR REPLACE TEMP TABLE _oth_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(file, chr(92), '/'), 'data/([0-9]{4})/raw/oth[0-9]{2}\.zip$', 1), '') AS INTEGER) AS cycle,
    CAST(NULL AS BIGINT) AS row_count,
    min(replace(file, chr(92), '/')) AS source_path,
    now() AS loaded_at
FROM glob('data/*/raw/oth*.zip')
GROUP BY 1;

DELETE FROM fec_oth_snapshot
WHERE cycle IN (SELECT cycle FROM _oth_counts);

INSERT INTO fec_oth_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _oth_counts
WHERE cycle IS NOT NULL;
