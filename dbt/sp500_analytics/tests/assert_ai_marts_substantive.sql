{{ config(severity='warn') }}

-- Guard (warn-level): AI marts with fewer than 25 rows are suspiciously thin for a
-- 5-year, 500-company scope — usually a partial extraction run (credit ran out) or a
-- --limit that was too small. Warns rather than fails so CI's tiny synthetic sample
-- still builds; on real data this warning means "re-run the extractors".

with counts as (
    select 'mart_ai_commitments'    as mart, count(*) as n from {{ ref('mart_ai_commitments') }}
    union all
    select 'mart_ai_material_facts' as mart, count(*) as n from {{ ref('mart_ai_material_facts') }}
    union all
    select 'mart_ai_events'         as mart, count(*) as n from {{ ref('mart_ai_events') }}
)

select mart, n
from counts
where n < 25
