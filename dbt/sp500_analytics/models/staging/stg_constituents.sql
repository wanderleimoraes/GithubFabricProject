with source as (
    select * from {{ source('bronze', 'sp500_constituents') }}
)

select
    ticker,
    company_name,
    gics_sector,
    gics_sub_industry,
    cik
from source
where ticker is not null
