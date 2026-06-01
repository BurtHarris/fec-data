{{ config(tags=['early_quality', 'fec_code_shape'], severity='warn') }}

with code_shape_violations as (
    select
        'indiv' as table_name,
        'AMNDT_IND' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(AMNDT_IND), '') = ''
       or not regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')

    union all

    select
        'indiv' as table_name,
        'RPT_TP' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(RPT_TP), '') = ''
       or not regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select
        'indiv' as table_name,
        'TRANSACTION_PGI' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(TRANSACTION_PGI), '') <> ''
            and not regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')

    union all

    select
        'indiv' as table_name,
        'TRANSACTION_TP' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(TRANSACTION_TP), '') = ''
       or not regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select
        'indiv' as table_name,
        'ENTITY_TP' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(ENTITY_TP), '') = ''
       or not regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')

    union all

    select
        'indiv' as table_name,
        'IMAGE_NUM' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(IMAGE_NUM), '') <> ''
      and not regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')

        union all

        select
                'indiv' as table_name,
                'OTHER_ID' as column_name,
                count(*) as invalid_count
        from {{ ref('indiv') }}
        where coalesce(trim(OTHER_ID), '') <> ''
            and not regexp_matches(
                upper(trim(OTHER_ID)),
                '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$'
            )

    union all

    select
        'indiv' as table_name,
        'MEMO_CD' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where coalesce(trim(MEMO_CD), '') <> ''
      and upper(trim(MEMO_CD)) <> 'X'

    union all

    select
        'indiv' as table_name,
        'SUB_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('indiv') }}
    where SUB_ID is null
       or SUB_ID <= 0
)
select
    table_name,
    column_name,
    invalid_count
from code_shape_violations
where invalid_count > 0
