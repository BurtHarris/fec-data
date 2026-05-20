-- Baseline snapshot for indiv using raw zip files.
-- For large-table safety in early phases, this records cycle/source availability
-- with row_count left NULL until incremental counting is introduced.

CREATE OR REPLACE TEMP TABLE _indiv_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(file, chr(92), '/'), 'data/([0-9]{4})/raw/indiv[0-9]{2}\.zip$', 1), '') AS INTEGER) AS cycle,
    CAST(NULL AS BIGINT) AS row_count,
    min(replace(file, chr(92), '/')) AS source_path,
    'raw-zip-baseline' AS load_mode,
    now() AS loaded_at
FROM glob('data/*/raw/indiv*.zip')
GROUP BY 1;

DELETE FROM fec_indiv_snapshot
WHERE cycle IN (SELECT cycle FROM _indiv_counts);

INSERT INTO fec_indiv_snapshot (cycle, row_count, source_path, load_mode, loaded_at)
SELECT cycle, row_count, source_path, load_mode, loaded_at
FROM _indiv_counts
WHERE cycle IS NOT NULL;
