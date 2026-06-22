-- Singular test: mart_fundamentals must have exactly one row per (ticker, period_end).
-- Returns offending rows; the test passes when zero rows are returned.

select
    ticker,
    period_end,
    count(*) as n_rows
from {{ ref('mart_fundamentals') }}
group by ticker, period_end
having count(*) > 1
