-- Gold dimension: one row per company (ticker).
-- The hub of the star schema — every fact mart (prices, fundamentals,
-- ai_commitments) relates many-to-one to this table on `ticker`. Built in the
-- warehouse (not as a Power BI DAX/Power Query table) so it stays a real Delta
-- table that Fabric Direct Lake can read natively.

with constituents as (
    select * from {{ ref('stg_constituents') }}
)

select
    ticker,
    company_name,
    gics_sector,
    gics_sub_industry,
    cik
from constituents
