{{
    config(
        materialized = 'incremental',
        unique_key = ['ticker', 'trade_date'],
        incremental_strategy = 'merge' if target.type == 'databricks' else 'delete+insert',
        post_hook = optimize_delta('ticker, trade_date'),
    )
}}

-- Gold: daily price features joined to company reference data.
-- Powers the stock-price-over-time dashboard.
--
-- INCREMENTAL: prices are a time-series fact that grows by trading day, so we don't
-- rebuild all history every run — we load only rows newer than what's already in the
-- table. This is the pattern you use on large, resource-heavy data (e.g. a bank's
-- transactions): full refresh once, then cheap daily appends.
--   - First run (or `--full-refresh`): builds the whole table.
--   - Later runs: is_incremental() is true → only trade_date > current max is processed,
--     then merged (Databricks) / delete+insert (DuckDB) on the (ticker, trade_date) key
--     so re-loaded days are replaced, not duplicated.
-- Moving averages / returns stay correct because int_prices_with_returns computes the
-- windows over full history; we only filter which rows get written here.

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

{% if is_incremental() %}
    -- only new trading days; the lookback keeps recent days re-checked for late updates
    where p.trade_date > (select max(trade_date) from {{ this }})
{% endif %}
