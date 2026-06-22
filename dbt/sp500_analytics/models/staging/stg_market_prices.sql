with source as (
    select * from {{ source('bronze', 'market_prices') }}
)

select
    ticker,
    cast(trade_date as date)   as trade_date,
    cast(open as double)       as open,
    cast(high as double)       as high,
    cast(low as double)        as low,
    cast(close as double)      as close,
    cast(adj_close as double)  as adj_close,
    cast(volume as bigint)     as volume
from source
where close is not null
