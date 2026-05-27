LOAD zipfs;
DROP TABLE IF EXISTS {TARGET_TABLE};
CREATE TABLE {TARGET_TABLE} AS
SELECT
    CMTE_ID,
    CMTE_NM,
    TRES_NM,
    CMTE_ST1,
    CMTE_ST2,
    CMTE_CITY,
    CMTE_ST,
    CMTE_ZIP,
    CMTE_DSGN,
    CMTE_TP,
    CMTE_PTY_AFFILIATION,
    CMTE_FILING_FREQ,
    ORG_TP,
    CONNECTED_ORG_NM,
    CAND_ID
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
        'CMTE_NM':'VARCHAR',
        'TRES_NM':'VARCHAR',
        'CMTE_ST1':'VARCHAR',
        'CMTE_ST2':'VARCHAR',
        'CMTE_CITY':'VARCHAR',
        'CMTE_ST':'VARCHAR',
        'CMTE_ZIP':'VARCHAR',
        'CMTE_DSGN':'VARCHAR',
        'CMTE_TP':'VARCHAR',
        'CMTE_PTY_AFFILIATION':'VARCHAR',
        'CMTE_FILING_FREQ':'VARCHAR',
        'ORG_TP':'VARCHAR',
        'CONNECTED_ORG_NM':'VARCHAR',
        'CAND_ID':'VARCHAR'
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
