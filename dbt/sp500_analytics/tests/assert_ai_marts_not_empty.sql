-- Guard: the AI marts are the thesis of this project. An empty one means the
-- extraction layer silently failed (e.g. the LLM run died on an API/credit error and
-- wrote a schema-only file) — fail loudly instead of shipping a hollow dashboard.
-- Lesson learned the hard way: the deployed report once showed stale synthetic
-- numbers because nothing checked that the real tables actually had rows.

with counts as (
    select 'mart_ai_commitments'    as mart, count(*) as n from {{ ref('mart_ai_commitments') }}
    union all
    select 'mart_ai_material_facts' as mart, count(*) as n from {{ ref('mart_ai_material_facts') }}
    union all
    select 'mart_ai_events'         as mart, count(*) as n from {{ ref('mart_ai_events') }}
)

select mart, n
from counts
where n = 0
