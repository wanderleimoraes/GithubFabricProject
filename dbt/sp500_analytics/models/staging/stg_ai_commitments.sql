with source as (
    select * from {{ source('bronze', 'ai_commitments') }}
),

constituents as (
    select ticker, company_name from {{ ref('stg_constituents') }}
)

select
    s.ticker,
    c.company_name,
    cast(s.event_date as date)   as event_date,
    s.commitment_text,
    cast(s.amount_usd as double) as amount_usd,
    s.category,
    s.source_url,
    cast(s.confidence as double) as confidence
from source s
left join constituents c on s.ticker = c.ticker
