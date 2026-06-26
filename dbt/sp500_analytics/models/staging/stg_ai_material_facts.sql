with source as (
    select * from {{ source('bronze', 'ai_material_facts') }}
),

constituents as (
    select ticker, company_name, gics_sector from {{ ref('stg_constituents') }}
)

select
    s.ticker,
    c.company_name,
    c.gics_sector,
    cast(s.fact_date as date)    as fact_date,
    s.headline,
    s.fact_text,
    s.context,
    s.category,
    cast(s.amount_usd as double) as amount_usd,
    s.significance,
    s.form,
    s.filing_item,
    s.accession_number,
    s.source_url
from source s
left join constituents c on s.ticker = c.ticker
