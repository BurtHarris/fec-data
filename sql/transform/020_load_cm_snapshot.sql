-- Load per-cycle row counts for committee master files from staging.
-- Reads all available cycle files at data/{cycle}/staging/cm.txt.

CREATE OR REPLACE TEMP TABLE _cm_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(filename, '\\', '/'), '(^|/)data/([0-9]{4})/staging/cm\\.txt$', 2), '') AS INTEGER) AS cycle,
    count(*) AS row_count,
    min(filename) AS source_path,
    now() AS loaded_at
FROM read_csv_auto(
    'data/*/staging/cm.txt',
    delim='|',
    header=false,
    all_varchar=true,
    filename=true,
    union_by_name=true
)
GROUP BY 1;

DELETE FROM fec_cm_snapshot
WHERE cycle IN (SELECT cycle FROM _cm_counts);

INSERT INTO fec_cm_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _cm_counts
WHERE cycle IS NOT NULL;
