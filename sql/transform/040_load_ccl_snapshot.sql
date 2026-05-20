-- Load per-cycle row counts for candidate-committee linkage files from silver.
-- Reads all available cycle files at data/{cycle}/silver/ccl.txt.

CREATE OR REPLACE TEMP TABLE _ccl_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(filename, chr(92), '/'), '(^|/)data/([0-9]{4})/silver/ccl\.txt$', 2), '') AS INTEGER) AS cycle,
    count(*) AS row_count,
    min(filename) AS source_path,
    now() AS loaded_at
FROM read_csv_auto(
    'data/*/silver/**/[cC][cC][lL]*.[tT][xX][tT]',
    delim='|',
    header=false,
    all_varchar=true,
    filename=true,
    union_by_name=true
)
GROUP BY 1;

DELETE FROM fec_ccl_snapshot
WHERE cycle IN (SELECT cycle FROM _ccl_counts);

INSERT INTO fec_ccl_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _ccl_counts
WHERE cycle IS NOT NULL;


