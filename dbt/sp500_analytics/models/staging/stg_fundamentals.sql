with source as (
    select * from {{ source('bronze', 'fundamentals') }}
)

select
    ticker,
    cik,
    tag,
    unit,
    cast(value as double)          as value,
    cast(fiscal_year as integer)   as fiscal_year,
    fiscal_period,
    form,
    cast(period_start as date)     as period_start,
    cast(period_end as date)       as period_end,
    cast(filed as date)            as filed_date
from source
where value is not null
  and form in ('10-K', '10-Q')
