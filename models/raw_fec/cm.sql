{{ config(alias=fec_table_alias('cm')) }}

-- Committee master. dbt owns table creation; this select defines table contents.
select
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
from read_csv(
    '{{ fec_source_path("cm", "cm.txt") }}',
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
)
