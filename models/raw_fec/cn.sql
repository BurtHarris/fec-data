{{ config(alias=fec_table_alias('cn')) }}

-- Candidate master. String-to-number casts are kept close to the raw load.
select
    CAND_ID,
    CAND_NAME,
    CAND_PTY_AFFILIATION,
    try_cast(case when length(trim(CAND_ELECTION_YR)) = 4 then trim(CAND_ELECTION_YR) end as smallint) as CAND_ELECTION_YR,
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
    nullif(substr(trim(CAND_ZIP), 1, 5), '') as CAND_ZIP
from read_csv(
    '{{ fec_source_path("cn", "cn.txt") }}',
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
)
