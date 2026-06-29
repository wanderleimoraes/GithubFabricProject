# Engineering techniques in this project (review / interview notes)

Concise reference for the data-engineering patterns implemented here, why they matter,
and how to talk about them.

## Incremental models (`materialized = 'incremental'`)

`dbt/sp500_analytics/models/marts/mart_prices.sql`

Time-series facts (prices; in banking, transactions) grow by day. Rebuilding all
history every run wastes compute. Incremental = full load once, then process only new
rows.

- **Partition pruning** — `{% if is_incremental() %} where trade_date > (select max(trade_date) from {{ this }}) {% endif %}` scans only new days, not the whole history.
- **Merge strategy** — `unique_key=['ticker','trade_date']` so re-loaded days are
  upserted, not duplicated. `incremental_strategy = 'merge'` on Databricks (MERGE INTO),
  `'delete+insert'` on DuckDB.
- **Cross-engine portability** — the strategy is chosen by `target.type`, so the same
  model runs on DuckDB (local/CI) and Databricks (cloud) without edits.
- **Correctness** — moving averages / returns are computed upstream in
  `int_prices_with_returns` over full history, so the rows written incrementally still
  carry correct window values.
- Verified: adding one trading day appended 3 rows (900 → 903), no duplication.

> *"For large fact tables I materialize incrementally: full load once, then each run
> prunes to new partitions (`where date > max`) and merges on the business key.
> Strategy is adapter-aware — MERGE on Databricks, delete+insert on DuckDB — and the
> derived windows stay correct because they're computed upstream over full history."*

## Delta optimization via post-hooks

`macros/optimize_delta.sql` + each mart's `post_hook`

After building each Gold table on Databricks: `OPTIMIZE <table> ZORDER BY (...)`.
- **OPTIMIZE** compacts the many small Parquet files dbt writes into larger ones.
- **ZORDER** clusters rows by the column you filter on most (`ticker` / `trade_date` /
  `event_date`) → less data scanned by the SQL warehouse and Power BI Direct Lake.
- Guarded to `target.type == 'databricks'` so it's a no-op on DuckDB (local/CI).

## Clean schema names across engines

`macros/generate_schema_name.sql`

dbt's default concatenates profile + model schema (`gold_gold`). The override keeps the
DuckDB concatenation (`main_silver`/`main_gold`, which local tooling depends on) but
uses the custom schema as-is on Databricks → clean `sp500.silver` / `sp500.gold`.

## Medallion + reproducibility

Bronze (raw, precious) → Silver (views: cleaned/typed/deduped) → Gold (tables: marts).
Silver/Gold are **derived and disposable** — `dbt build` regenerates them from Bronze, so
rebuilds are safe/idempotent. Only Bronze and the LLM extractions are irreplaceable.

## Testing & semantic grounding

- dbt tests: `not_null` / `unique` on keys, plus a singular grain test
  (`tests/assert_mart_fundamentals_grain.sql`).
- Hand-authored semantic layer (`nl_query/ontology.py`): entities, relationships, metric
  glossary, worked Q→SQL examples — grounds the LLM so it answers complex multi-table,
  comparative, temporal questions. Blueprint for the native Fabric IQ Ontology.

## Data publishing policy (what's safe to make public)

- `data/`, `*.parquet`, `*.duckdb` are git-ignored → raw/real data never enters the repo.
- **Only exception:** `nl_query/sample_data/*.parquet` ships with the deployed app. Keep
  this a **small, sampled or synthetic** snapshot — do not export the full real dataset
  there (size bloat + Yahoo/yfinance redistribution terms). SEC EDGAR data is public
  domain; bulk market-price redistribution is a gray area.
