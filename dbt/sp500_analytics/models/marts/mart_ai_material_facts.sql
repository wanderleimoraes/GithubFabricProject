-- Gold: material AI facts (LLM-extracted from 8-K filings), one fact per row.
-- Deliberately rich and source-linked so a reader can click through to the filing
-- and interpret each fact for themselves. Powers the "AI material facts" table and
-- timeline, and is a primary table for the NL Q&A layer.

with facts as (
    select * from {{ ref('stg_ai_material_facts') }}
)

select
    ticker,
    company_name,
    gics_sector,
    fact_date,
    extract(year from fact_date)  as fact_year,
    headline,
    fact_text,
    context,
    category,
    amount_usd,
    significance,
    form,
    filing_item,
    accession_number,
    source_url
from facts
