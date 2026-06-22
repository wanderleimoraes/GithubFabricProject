-- Industry-wide AI events come from a curated seed file, not an ingested source.
with seed as (
    select * from {{ ref('ai_industry_events') }}
)

select
    cast(event_date as date) as event_date,
    vendor,
    event_name,
    category,
    related_ticker,
    significance,
    url
from seed
