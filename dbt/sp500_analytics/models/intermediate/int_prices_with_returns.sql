-- Enrich daily prices with returns and moving averages (price feature layer).

with prices as (
    select * from {{ ref('stg_market_prices') }}
)

select
    ticker,
    trade_date,
    open,
    high,
    low,
    close,
    adj_close,
    volume,
    adj_close / nullif(lag(adj_close) over w, 0) - 1            as daily_return,
    avg(adj_close) over (
        partition by ticker order by trade_date
        rows between 49 preceding and current row
    )                                                          as ma_50,
    avg(adj_close) over (
        partition by ticker order by trade_date
        rows between 199 preceding and current row
    )                                                          as ma_200
from prices
window w as (partition by ticker order by trade_date)
