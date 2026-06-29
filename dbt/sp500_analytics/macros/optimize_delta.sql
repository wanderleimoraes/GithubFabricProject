{#
    post_hook helper: compact + cluster a Gold Delta table after dbt builds it.

    On Databricks, dbt writes many small Parquet files; OPTIMIZE compacts them and
    (optionally) ZORDER clusters the data by the columns we filter on most, which
    speeds up the SQL warehouse and Power BI Direct Lake. These commands are
    Databricks-only, so on DuckDB (local/CI) this renders to nothing and dbt skips
    the empty hook.

    Usage in a model:  {{ config(post_hook = optimize_delta('ticker')) }}
#}
{% macro optimize_delta(zorder=none) %}
    {%- if target.type == 'databricks' -%}
        optimize {{ this }}{% if zorder %} zorder by ({{ zorder }}){% endif %}
    {%- endif -%}
{% endmacro %}
