{#
    Control how model schemas are named.

    dbt's built-in behavior concatenates the profile's schema with the model's
    custom `+schema:` config, e.g. profile `gold` + model `silver` => `gold_silver`.
    That is noisy in the cloud warehouse (we want clean `sp500.silver` /
    `sp500.gold`), but the local DuckDB tooling (nl_query app, export script)
    already depends on the concatenated `main_silver` / `main_gold` names.

    So: keep the default concatenation for DuckDB, and use the custom schema
    name as-is for every other target (Databricks, Fabric). This gives clean
    catalog.schema.table names in the cloud without disturbing local dev.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.type == 'duckdb' -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
