-- {{ config(tags=['early_quality', 'fec_code_shape'], severity='warn') }}

with code_shape_violations as (
    -- oth checks (same layout as indiv)
    select 'oth' as table_name, 'AMNDT_IND' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(AMNDT_IND), '') = ''
       or not regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')

    union all

    select 'oth' as table_name, 'RPT_TP' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(RPT_TP), '') = ''
       or not regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select 'oth' as table_name, 'TRANSACTION_PGI' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(TRANSACTION_PGI), '') <> ''
      and not regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')

    union all

    select 'oth' as table_name, 'TRANSACTION_TP' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(TRANSACTION_TP), '') = ''
       or not regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select 'oth' as table_name, 'ENTITY_TP' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(ENTITY_TP), '') = ''
       or not regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')

    union all

    select 'oth' as table_name, 'IMAGE_NUM' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(IMAGE_NUM), '') <> ''
      and not regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')

      union all

      select 'oth' as table_name, 'OTHER_ID' as column_name, count(*) as invalid_count
      from {{ ref('oth') }}
      where coalesce(trim(OTHER_ID), '') <> ''
         and not regexp_matches(
            upper(trim(OTHER_ID)),
            '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$'
         )

    union all

    select 'oth' as table_name, 'MEMO_CD' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where coalesce(trim(MEMO_CD), '') <> ''
      and upper(trim(MEMO_CD)) <> 'X'

    union all

    select 'oth' as table_name, 'SUB_ID' as column_name, count(*) as invalid_count
    from {{ ref('oth') }}
    where SUB_ID is null
       or SUB_ID <= 0

    union all

    -- pas2 checks (same layout as indiv plus CAND_ID)
    select 'pas2' as table_name, 'AMNDT_IND' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(AMNDT_IND), '') = ''
       or not regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')

    union all

    select 'pas2' as table_name, 'RPT_TP' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(RPT_TP), '') = ''
       or not regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select 'pas2' as table_name, 'TRANSACTION_PGI' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(TRANSACTION_PGI), '') <> ''
      and not regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')

    union all

    select 'pas2' as table_name, 'TRANSACTION_TP' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(TRANSACTION_TP), '') = ''
       or not regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select 'pas2' as table_name, 'ENTITY_TP' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(ENTITY_TP), '') = ''
       or not regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')

    union all

    select 'pas2' as table_name, 'IMAGE_NUM' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(IMAGE_NUM), '') <> ''
      and not regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')

      union all

      select 'pas2' as table_name, 'OTHER_ID' as column_name, count(*) as invalid_count
      from {{ ref('pas2') }}
      where coalesce(trim(OTHER_ID), '') <> ''
         and not regexp_matches(
            upper(trim(OTHER_ID)),
            '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$'
         )

    union all

    select 'pas2' as table_name, 'MEMO_CD' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where coalesce(trim(MEMO_CD), '') <> ''
      and upper(trim(MEMO_CD)) <> 'X'

    union all

    select 'pas2' as table_name, 'SUB_ID' as column_name, count(*) as invalid_count
    from {{ ref('pas2') }}
    where SUB_ID is null
       or SUB_ID <= 0

    union all

    -- oppexp checks (no TRANSACTION_TP in this layout)
    select 'oppexp' as table_name, 'AMNDT_IND' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(AMNDT_IND), '') = ''
       or not regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')

    union all

    select 'oppexp' as table_name, 'RPT_TP' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(RPT_TP), '') = ''
       or not regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')

    union all

    select 'oppexp' as table_name, 'TRANSACTION_PGI' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(TRANSACTION_PGI), '') <> ''
      and not regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')

    union all

    select 'oppexp' as table_name, 'ENTITY_TP' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(ENTITY_TP), '') = ''
       or not regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')

    union all

    select 'oppexp' as table_name, 'IMAGE_NUM' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(IMAGE_NUM), '') <> ''
      and not regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')

    union all

    select 'oppexp' as table_name, 'MEMO_CD' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where coalesce(trim(MEMO_CD), '') <> ''
      and upper(trim(MEMO_CD)) <> 'X'

    union all

    select 'oppexp' as table_name, 'SUB_ID' as column_name, count(*) as invalid_count
    from {{ ref('oppexp') }}
    where SUB_ID is null
       or SUB_ID <= 0
)
select
    table_name,
    column_name,
    invalid_count
from code_shape_violations
where invalid_count > 0
