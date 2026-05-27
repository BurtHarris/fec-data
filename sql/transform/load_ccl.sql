LOAD zipfs;
DROP TABLE IF EXISTS {TARGET_TABLE};
CREATE TABLE {TARGET_TABLE} AS
SELECT
    CAND_ID,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(CAND_ELECTION_YR)) = 4 THEN TRIM(CAND_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS CAND_ELECTION_YR,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(FEC_ELECTION_YR)) = 4 THEN TRIM(FEC_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS FEC_ELECTION_YR,
    CMTE_ID,
    CMTE_TP,
    CMTE_DSGN,
    TRY_CAST(NULLIF(TRIM(LINKAGE_ID), '') AS BIGINT) AS LINKAGE_ID
FROM read_csv(
    '{SOURCE_PATH}',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CAND_ID':'VARCHAR',
        'CAND_ELECTION_YR':'VARCHAR',
        'FEC_ELECTION_YR':'VARCHAR',
        'CMTE_ID':'VARCHAR',
        'CMTE_TP':'VARCHAR',
        'CMTE_DSGN':'VARCHAR',
        'LINKAGE_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history (
    load_id,
    cycle,
    table_name,
    source_zip_path,
    source_entry_name,
    target_table_name,
    row_count,
    loaded_at
)
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1),
    {CYCLE},
    '{TABLE_NAME}',
    '{ZIP_PATH}',
    {ENTRY_NAME_SQL},
    '{TARGET_TABLE}',
    (SELECT COUNT(*) FROM {TARGET_TABLE}),
    NOW();
