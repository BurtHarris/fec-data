{{ config(tags=['early_quality', 'fec_code_shape'], severity='warn') }}

with code_shape_violations as (
    -- cm checks
    select
        'cm' as table_name,
        'CMTE_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where coalesce(trim(CMTE_ID), '') = ''
      or not regexp_matches(upper(trim(CMTE_ID)), '^C[0-9]{8}$')

    union all

    select
        'cm' as table_name,
        'CMTE_DSGN' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where coalesce(trim(CMTE_DSGN), '') = ''
      or not regexp_matches(upper(trim(CMTE_DSGN)), '^[ABDJPU]$')

    union all

    select
        'cm' as table_name,
        'CMTE_TP' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where coalesce(trim(CMTE_TP), '') = ''
      or not regexp_matches(upper(trim(CMTE_TP)), '^[A-Z]$')

    union all

    select
        'cm' as table_name,
        'CMTE_FILING_FREQ' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where coalesce(trim(CMTE_FILING_FREQ), '') <> ''
      and not regexp_matches(upper(trim(CMTE_FILING_FREQ)), '^[ADMQTW]$')

    union all

    select
        'cm' as table_name,
        'ORG_TP' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where coalesce(trim(ORG_TP), '') <> ''
      and not regexp_matches(upper(trim(ORG_TP)), '^[CLMTVW]$')

    union all

    select
        'cm' as table_name,
        'CAND_ID_MISSING_FOR_HSP' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where upper(trim(CMTE_TP)) in ('H', 'S', 'P')
      and coalesce(trim(CAND_ID), '') = ''

    union all

    select
        'cm' as table_name,
        'CAND_ID_BAD_SHAPE_FOR_HSP' as column_name,
        count(*) as invalid_count
    from {{ ref('cm') }}
    where upper(trim(CMTE_TP)) in ('H', 'S', 'P')
      and (
        coalesce(trim(CAND_ID), '') <> ''
        and not regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')
      )

    union all

    -- cn checks
    select
        'cn' as table_name,
        'CAND_ID' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where coalesce(trim(CAND_ID), '') = ''
      or not regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')

    union all

    select
        'cn' as table_name,
        'CAND_OFFICE' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where coalesce(trim(CAND_OFFICE), '') = ''
      or not regexp_matches(upper(trim(CAND_OFFICE)), '^[HSP]$')

    union all

    select
        'cn' as table_name,
        'CAND_OFFICE_ST' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where upper(trim(CAND_OFFICE)) in ('H', 'S')
      and not regexp_matches(trim(CAND_OFFICE_ST), '^[A-Z]{2}$')

    union all

    select
        'cn' as table_name,
        'CAND_STATUS' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where coalesce(trim(CAND_STATUS), '') <> ''
      and not regexp_matches(upper(trim(CAND_STATUS)), '^[CNPF]$')

    union all

    select
        'cn' as table_name,
        'CAND_ICI' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where coalesce(trim(CAND_ICI), '') <> ''
      and not regexp_matches(upper(trim(CAND_ICI)), '^[CIO]$')

    union all

    select
        'cn' as table_name,
        'CAND_PCC' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where coalesce(trim(CAND_PCC), '') <> ''
      and not regexp_matches(upper(trim(CAND_PCC)), '^C[0-9]{8}$')

    union all

    select
        'cn' as table_name,
        'CAND_ELECTION_YR' as column_name,
        count(*) as invalid_count
    from {{ ref('cn') }}
    where CAND_ELECTION_YR is null
      or CAND_ELECTION_YR < 1900
      or CAND_ELECTION_YR > 2100
      or (CAND_ELECTION_YR % 2) <> 0
)
select
    table_name,
    column_name,
    invalid_count
from code_shape_violations
where invalid_count > 0
