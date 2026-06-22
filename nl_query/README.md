# Natural-language Q&A layer

A Streamlit text-to-SQL app over the Gold marts.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run nl_query/app.py
```

## How it works
1. `schema_context.py` builds a compact schema description from the dbt
   `catalog.json` + `manifest.json` (run `dbt docs generate` first; otherwise a
   static fallback is used).
2. The question + schema go to Claude, which returns a single read-only SQL query.
3. The query is validated (SELECT-only, allow-listed tables) and executed on DuckDB
   locally (swap to the Databricks SQL connector for production).
4. Claude writes a short narrative answer and the app auto-renders a chart.

## Safety
- Only `mart_*` tables are exposed.
- Generated SQL must start with `SELECT` and is rejected if it contains DDL/DML keywords.
- DuckDB is opened read-only.

## Swapping to Databricks
Replace the `duckdb.connect(...)` execution with `databricks-sql-connector` using the
`DATABRICKS_*` env vars; everything else (prompting, validation, narration) is unchanged.
