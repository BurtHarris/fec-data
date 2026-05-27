LOAD zipfs;
DROP TABLE IF EXISTS {TARGET_TABLE};
CREATE TABLE {TARGET_TABLE} AS
SELECT
    CAND_ID,
    CAND_NAME,
    CAND_PTY_AFFILIATION,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(CAND_ELECTION_YR)) = 4 THEN TRIM(CAND_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS CAND_ELECTION_YR,
    CAND_OFFICE_ST,
    CAND_OFFICE,
    CAND_OFFICE_DISTRICT,
    CAND_ICI,
    CAND_STATUS,
    CAND_PCC,
    CAND_ST1,
    CAND_ST2,
    CAND_CITY,
    CAND_ST,
    CAND_ZIP
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
        'CAND_NAME':'VARCHAR',
        'CAND_PTY_AFFILIATION':'VARCHAR',
        'CAND_ELECTION_YR':'VARCHAR',
        'CAND_OFFICE_ST':'VARCHAR',
        'CAND_OFFICE':'VARCHAR',
        'CAND_OFFICE_DISTRICT':'VARCHAR',
        'CAND_ICI':'VARCHAR',
        'CAND_STATUS':'VARCHAR',
        'CAND_PCC':'VARCHAR',
        'CAND_ST1':'VARCHAR',
        'CAND_ST2':'VARCHAR',
        'CAND_CITY':'VARCHAR',
        'CAND_ST':'VARCHAR',
        'CAND_ZIP':'VARCHAR'
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
