-- Gold: AI investment commitments (LLM-extracted) sliced against fundamentals so
-- commitments can be compared to revenue, cash flow, profit, etc.
-- Powers the "AI investment commitment" dashboard.

with commitments as (
    select * from {{ ref('stg_ai_commitments') }}
),

latest_fundamentals as (
    select
        ticker,
        revenue,
        net_income,
        operating_cash_flow,
        total_assets,
        row_number() over (partition by ticker order by period_end desc) as rn
    from {{ ref('mart_fundamentals') }}
)

select
    c.ticker,
    c.company_name,
    c.event_date,
    c.commitment_text,
    c.amount_usd,
    c.category,
    c.source_url,
    c.confidence,
    f.revenue                                              as latest_revenue,
    f.operating_cash_flow                                 as latest_operating_cash_flow,
    case when f.revenue > 0
         then c.amount_usd / f.revenue end                as commitment_to_revenue_ratio,
    case when f.operating_cash_flow > 0
         then c.amount_usd / f.operating_cash_flow end    as commitment_to_ocf_ratio
from commitments c
left join latest_fundamentals f on c.ticker = f.ticker and f.rn = 1
