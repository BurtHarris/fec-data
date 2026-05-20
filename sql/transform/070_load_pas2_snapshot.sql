-- Baseline snapshot for pas2 using raw zip files.
-- Row-level counting is deferred until extraction/loading for this family is enabled.

CREATE OR REPLACE TEMP TABLE _pas2_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(file, chr(92), '/'), 'data/([0-9]{4})/raw/pas2[0-9]{2}\.zip$', 1), '') AS INTEGER) AS cycle,
    CAST(NULL AS BIGINT) AS row_count,
    min(replace(file, chr(92), '/')) AS source_path,
    now() AS loaded_at
FROM glob('data/*/raw/pas2*.zip')
GROUP BY 1;

DELETE FROM fec_pas2_snapshot
WHERE cycle IN (SELECT cycle FROM _pas2_counts);

INSERT INTO fec_pas2_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _pas2_counts
WHERE cycle IS NOT NULL;
