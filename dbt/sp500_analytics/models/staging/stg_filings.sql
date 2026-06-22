with source as (
    select * from {{ source('bronze', 'filings') }}
)

select
    ticker,
    cik,
    form,
    cast(filing_date as date)  as filing_date,
    cast(report_date as date)  as report_date,
    accession_number,
    primary_document,
    items,
    document_url
from source
