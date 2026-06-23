-- Gold: one row per company per fiscal period, canonical metrics pivoted to columns.
-- Powers the company-vs-company comparison dashboard and the NL Q&A layer.

with normalized as (
    select * from {{ ref('int_fundamentals_normalized') }}
),

constituents as (
    select * from {{ ref('stg_constituents') }}
),

pivoted as (
    select
        ticker,
        cik,
        fiscal_year,
        fiscal_period,
        period_end,
        max(case when canonical_metric = 'revenue'             then value end) as revenue,
        max(case when canonical_metric = 'net_income'          then value end) as net_income,
        max(case when canonical_metric = 'operating_income'    then value end) as operating_income,
        max(case when canonical_metric = 'rnd_expense'         then value end) as rnd_expense,
        max(case when canonical_metric = 'capex'               then value end) as capex,
        max(case when canonical_metric = 'operating_cash_flow' then value end) as operating_cash_flow,
        max(case when canonical_metric = 'total_assets'        then value end) as total_assets,
        max(case when canonical_metric = 'total_liabilities'   then value end) as total_liabilities,
        max(case when canonical_metric = 'stockholders_equity' then value end) as stockholders_equity,
        max(case when canonical_metric = 'cash_and_equivalents' then value end) as cash_and_equivalents,
        max(case when canonical_metric = 'eps_diluted'         then value end) as eps_diluted
    from normalized
    where fiscal_period = 'FY'
    group by ticker, cik, fiscal_year, fiscal_period, period_end
)

select
    p.*,
    c.company_name,
    c.gics_sector,
    c.gics_sub_industry,
    case when p.revenue > 0 then p.net_income / p.revenue end as net_margin,
    case when p.revenue > 0 then p.rnd_expense / p.revenue end as rnd_intensity
from pivoted p
left join constituents c on p.ticker = c.ticker
