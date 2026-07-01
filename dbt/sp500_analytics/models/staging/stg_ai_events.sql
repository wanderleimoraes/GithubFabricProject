-- Industry-wide AI events: LLM-structured from real GDELT news candidates
-- (ingestion/ai_industry_news -> extraction/ai_event_extractor -> bronze.ai_events).
-- Replaces the old hand-curated seed; every row carries a real source url + date.
with source as (
    select * from {{ source('bronze', 'ai_events') }}
)

select
    cast(event_date as date) as event_date,
    vendor,
    event_name,
    category,
    related_ticker,
    significance,
    url
from source
