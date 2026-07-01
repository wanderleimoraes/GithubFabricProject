-- Map messy raw US-GAAP XBRL tags to a small canonical metric set, and keep one
-- value per (ticker, period_end, metric) by preferring the most recently filed
-- observation. This is the core normalization that makes EDGAR data usable.

with facts as (
    select * from {{ ref('stg_fundamentals') }}
),

mapping as (
    select * from {{ ref('gaap_tag_mapping') }}
),

mapped as (
    select
        f.ticker,
        f.cik,
        m.canonical_metric,
        f.unit,
        f.value,
        f.fiscal_year,
        f.fiscal_period,
        f.period_start,
        f.period_end,
        f.filed_date
    from facts f
    inner join mapping m on f.tag = m.gaap_tag
    where f.unit in ('USD', 'USD/shares', 'shares')
),

deduped as (
    select
        *,
        row_number() over (
            partition by ticker, canonical_metric, period_end
            order by filed_date desc
        ) as rn
    from mapped
)

select
    ticker,
    cik,
    canonical_metric,
    value,
    fiscal_year,
    fiscal_period,
    period_start,
    period_end,
    filed_date
from deduped
where rn = 1
