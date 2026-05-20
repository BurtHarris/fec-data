-- Load per-cycle row counts for candidate master files from silver.
-- Reads all available cycle files at data/{cycle}/silver/cn.txt.

CREATE OR REPLACE TEMP TABLE _cn_counts AS
SELECT
    CAST(NULLIF(regexp_extract(replace(filename, chr(92), '/'), '(^|/)data/([0-9]{4})/silver/cn\.txt$', 2), '') AS INTEGER) AS cycle,
    count(*) AS row_count,
    min(filename) AS source_path,
    now() AS loaded_at
FROM read_csv_auto(
    'data/*/silver/cn.txt',
    delim='|',
    header=false,
    all_varchar=true,
    filename=true,
    union_by_name=true
)
GROUP BY 1;

DELETE FROM fec_cn_snapshot
WHERE cycle IN (SELECT cycle FROM _cn_counts);

INSERT INTO fec_cn_snapshot (cycle, row_count, source_path, loaded_at)
SELECT cycle, row_count, source_path, loaded_at
FROM _cn_counts
WHERE cycle IS NOT NULL;
