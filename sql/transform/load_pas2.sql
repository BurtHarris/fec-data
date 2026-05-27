LOAD zipfs;
DROP TABLE IF EXISTS {TARGET_TABLE};
CREATE TABLE {TARGET_TABLE} AS
SELECT
    CMTE_ID,
    AMNDT_IND,
    RPT_TP,
    TRANSACTION_PGI,
    IMAGE_NUM,
    TRANSACTION_TP,
    ENTITY_TP,
    NAME,
    CITY,
    STATE,
    ZIP_CODE,
    EMPLOYER,
    OCCUPATION,
    CAST(TRY_STRPTIME(NULLIF(TRIM(TRANSACTION_DT), ''), '%m%d%Y') AS DATE) AS TRANSACTION_DT,
    TRY_CAST(NULLIF(TRIM(TRANSACTION_AMT), '') AS DECIMAL(14,2)) AS TRANSACTION_AMT,
    OTHER_ID,
    CAND_ID,
    TRAN_ID,
    TRY_CAST(NULLIF(TRIM(FILE_NUM), '') AS BIGINT) AS FILE_NUM,
    MEMO_CD,
    MEMO_TEXT,
    TRY_CAST(NULLIF(TRIM(SUB_ID), '') AS BIGINT) AS SUB_ID
FROM read_csv(
    '{SOURCE_PATH}',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'AMNDT_IND':'VARCHAR',
        'RPT_TP':'VARCHAR',
        'TRANSACTION_PGI':'VARCHAR',
        'IMAGE_NUM':'VARCHAR',
        'TRANSACTION_TP':'VARCHAR',
        'ENTITY_TP':'VARCHAR',
        'NAME':'VARCHAR',
        'CITY':'VARCHAR',
        'STATE':'VARCHAR',
        'ZIP_CODE':'VARCHAR',
        'EMPLOYER':'VARCHAR',
        'OCCUPATION':'VARCHAR',
        'TRANSACTION_DT':'VARCHAR',
        'TRANSACTION_AMT':'VARCHAR',
        'OTHER_ID':'VARCHAR',
        'CAND_ID':'VARCHAR',
        'TRAN_ID':'VARCHAR',
        'FILE_NUM':'VARCHAR',
        'MEMO_CD':'VARCHAR',
        'MEMO_TEXT':'VARCHAR',
        'SUB_ID':'VARCHAR'
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
