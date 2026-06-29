{{ config(post_hook = optimize_delta('event_date')) }}

-- Gold: curated industry-wide AI events for chart overlays / tooltips
-- (e.g. "did MSFT move when GPT-4 launched?").

select
    event_date,
    vendor,
    event_name,
    category,
    related_ticker,
    significance,
    url
from {{ ref('stg_ai_events') }}
