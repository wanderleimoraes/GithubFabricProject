{{ config(post_hook = optimize_delta('date_day')) }}

-- Gold: explicit calendar dimension. Replaces Power BI's Auto date/time (which
-- creates a hidden LocalDateTable per date column and bloats the model). One
-- contiguous day-grain spine covering the project's lookback window plus headroom;
-- relate fact date columns (trade_date, period_end, event_date, fact_date) to
-- date_day and disable Auto date/time in the semantic model.
--
-- The spine generator is dialect-specific (DuckDB generate_series vs Databricks
-- sequence/explode), so it branches on the dbt target — a small example of writing
-- one model for two engines.

with spine as (

{% if target.type == 'databricks' %}
    select explode(sequence(
        to_date('2020-01-01'), to_date('2027-12-31'), interval 1 day
    )) as date_day
{% else %}
    select unnest(generate_series(
        date '2020-01-01', date '2027-12-31', interval 1 day
    ))::date as date_day
{% endif %}

)

select
    cast(date_day as date)                       as date_day,
    extract(year from date_day)                  as year,
    extract(quarter from date_day)               as quarter,
    extract(month from date_day)                 as month,
    extract(day from date_day)                   as day_of_month,
    cast(extract(year from date_day) as string) || '-Q'
        || cast(extract(quarter from date_day) as string)   as year_quarter,
    cast(extract(year from date_day) * 100
        + extract(month from date_day) as int)   as year_month,
    cast(date_day as date) = last_day(cast(date_day as date)) as is_month_end
from spine
