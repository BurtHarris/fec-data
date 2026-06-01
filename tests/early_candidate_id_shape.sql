{{ config(tags=['early_quality', 'fec_id_shape'], severity='warn') }}

with shape_violations as (
    select
        'ccl' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('ccl') }}
    where CAND_ID is not null
      and not regexp_matches(CAND_ID, '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')

    union all

    select
        'cm' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where CAND_ID is not null
      and not regexp_matches(CAND_ID, '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')

    union all

    select
        'cn' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where CAND_ID is not null
      and not regexp_matches(CAND_ID, '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')

    union all

    select
        'pas2' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('pas2') }}
    where CAND_ID is not null
      and not regexp_matches(CAND_ID, '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')

    union all

    select
        'weball' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('weball') }}
    where CAND_ID is not null
      and not regexp_matches(CAND_ID, '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')
)
select
    table_name,
    column_name,
    invalid_count
from shape_violations
where invalid_count > 0
