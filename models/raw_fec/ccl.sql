{{ config(alias=fec_table_alias('ccl')) }}

-- This model is a dbt version of sql/transform/load_ccl.sql.
-- dbt will materialize it as raw_fec.ccl_<cycle>.
with source_rows as (
    select *
    from read_csv(
        '{{ fec_source_path("ccl", "ccl.txt") }}',
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
    )
)
select
    CAND_ID,
    try_cast(case when length(trim(CAND_ELECTION_YR)) = 4 then trim(CAND_ELECTION_YR) end as smallint) as CAND_ELECTION_YR,
    try_cast(case when length(trim(FEC_ELECTION_YR)) = 4 then trim(FEC_ELECTION_YR) end as smallint) as FEC_ELECTION_YR,
    CMTE_ID,
    CMTE_TP,
    CMTE_DSGN,
    try_cast(nullif(trim(LINKAGE_ID), '') as bigint) as LINKAGE_ID
from source_rows
