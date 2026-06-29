{{ config(post_hook = optimize_delta('ticker, trade_date')) }}

-- Gold: daily price features joined to company reference data.
-- Powers the stock-price-over-time dashboard.

with prices as (
    select * from {{ ref('int_prices_with_returns') }}
),

constituents as (
    select * from {{ ref('stg_constituents') }}
)

select
    p.ticker,
    c.company_name,
    c.gics_sector,
    p.trade_date,
    p.close,
    p.adj_close,
    p.volume,
    p.daily_return,
    p.ma_50,
    p.ma_200
from prices p
left join constituents c on p.ticker = c.ticker
