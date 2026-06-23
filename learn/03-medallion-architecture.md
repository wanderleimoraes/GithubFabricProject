# Module 03 — Medallion architecture  💻 runs here

**Goal:** understand *why* a data pipeline is split into three layers, map those
layers to this project's actual files, and see the contrast between raw Bronze data
and finished Gold data with your own queries.

---

## Concept

### The problem: raw data is a mess

Raw data from external sources has problems:

- **Wrong types** — dates stored as strings, numbers as text.
- **Duplicate records** — the same fact filed twice under slightly different tags.
- **Inconsistent naming** — NVIDIA might be "NVIDIA", "NVDA Corp", or "nVidia" in
  different sources.
- **Mixed grain** — one row might be a daily price, another a quarterly total.

If you try to build a dashboard directly on raw data, you'll get wrong answers and
spend all your time debugging data quality instead of doing analytics.

**The Medallion architecture** solves this by splitting the pipeline into three named
layers, each with a clear purpose:

### Bronze — "raw as-is"

> *Keep it forever. Never change it.*

Bronze is an exact copy of what arrived from the source, with only two additions: a
load timestamp (`_ingested_at`) and the date the file was received. No cleaning, no
transformation. If something goes wrong downstream, you can always replay from Bronze.

In this project: the five Parquet files in `data/bronze/` that you generated in
Module 01. Written by the `ingestion/` Python scripts.

### Silver — "clean and conformed"

> *One clean version of the truth.*

Silver cleans, casts types, deduplicates, and standardises names. Every row is
valid; every column has the right type. If a company appears differently across
sources, Silver picks one canonical form.

Critically, Silver is **still atomic** — it hasn't been aggregated or combined in ways
that would lose flexibility. It's clean raw material, not a finished product.

In this project: the dbt **staging** and **intermediate** models (both materialised
as views in the `silver` schema). Staging does the 1-to-1 cleaning; intermediate
does the cross-source joining and complex reshaping.

### Gold — "business-ready"

> *Answer a specific question, fast.*

Gold is built for a specific audience and use case: a dashboard, a report, a machine-
learning feature table. It may aggregate, pivot, or pre-join things for speed. It has
tests and documentation. It's the layer Power BI and the NL Q&A app query.

In this project: the dbt **marts** (materialised as tables in the `gold` schema):
`mart_prices`, `mart_fundamentals`, `mart_ai_commitments`, `mart_ai_events`.

### Why three? Why not just two (or one)?

The key insight is that **different people need different levels of fidelity**:

- A data scientist might want to go back to Silver to build a custom aggregate that
  no existing mart covers.
- An analyst building a dashboard just wants Gold — pre-joined, pre-tested, fast.
- An auditor or compliance team wants Bronze — immutable proof of exactly what arrived.

With one layer, you'd have to serve everyone from the same dataset and make
compromises everywhere. With three, each layer is optimised for its audience.

---

## In this repo

The three layers map to the file system exactly:

```
Bronze  →  data/bronze/*/          (Parquet files, written by ingestion/)
Silver  →  models/staging/         (stg_*.sql — clean & cast each source)
           models/intermediate/    (int_*.sql — join, dedup, derive)
Gold    →  models/marts/           (mart_*.sql — business-ready, tested)
```

And to the DuckDB schemas after `dbt build`:

```
main_silver.stg_market_prices       ← Silver view
main_silver.int_prices_with_returns ← Silver view
main_gold.mart_prices               ← Gold table
```

Two files worth opening to see the layers in action:

- [`models/intermediate/int_prices_with_returns.sql`](../dbt/sp500_analytics/models/intermediate/int_prices_with_returns.sql)
  — reads from `ref('stg_market_prices')` (Silver entry) and adds `daily_return`,
  `ma_50`, `ma_200` via window functions. It enriches without aggregating — still
  one row per ticker per day.
- [`models/marts/mart_prices.sql`](../dbt/sp500_analytics/models/marts/mart_prices.sql)
  — reads from `ref('int_prices_with_returns')` and joins to
  `ref('stg_constituents')` to attach `company_name` and `gics_sector`. The finished
  Gold table: every column a dashboard would want, already joined, tested, and named
  clearly.

---

## Hands-on

Make sure you're in the dbt project folder with the env vars set (from Module 02):

```powershell
cd C:\dev\GithubFabricProject\dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
```

### 1. Compare Bronze to Silver to Gold for the same data

Open a Python prompt (`python`) and run these queries, one at a time:

**Bronze — raw Parquet:**
```python
import duckdb
con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")

# Raw Bronze: no company_name, no returns, raw column names
duckdb.sql("SELECT * FROM 'C:/dev/GithubFabricProject/data/bronze/market_prices/market_prices.parquet' LIMIT 3").show()
```

**Silver — cleaned, standard types:**
```python
# Silver: clean types, nulls filtered, same grain (one row per ticker per day)
con.sql("SELECT ticker, trade_date, close FROM main_silver.stg_market_prices LIMIT 3").show()
```

**Gold — business-ready with derived columns:**
```python
# Gold: company_name added, daily_return and moving averages computed
con.sql("SELECT company_name, trade_date, ROUND(close,2) AS close, ROUND(daily_return*100,3) AS daily_return_pct, ROUND(ma_50,2) AS ma_50 FROM main_gold.mart_prices ORDER BY company_name, trade_date LIMIT 5").show()
```

*What to notice:* same underlying data (MSFT daily prices), but three very different
views of it. Bronze is raw and messy-ish. Silver is clean but plain. Gold is enriched,
named for a human, and ready to drop straight into a dashboard.

### 2. See the dependency chain in the dbt DAG

```bash
dbt ls --select mart_prices --output name
```

This lists the full dependency tree that `mart_prices` depends on. You should see
something like:
```
sp500_analytics.stg_constituents
sp500_analytics.stg_market_prices
sp500_analytics.int_prices_with_returns
sp500_analytics.mart_prices
```

That chain — Bronze source → stg (Silver) → int (Silver) → mart (Gold) — *is* the
Medallion architecture in code.

### 3. (Optional) Check the schema in DuckDB directly

```python
# See all schemas and tables dbt created
con.sql("SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema LIKE 'main_%' ORDER BY table_schema, table_name").show()
```

You'll see `main_gold` (tables) and `main_silver` (views) — the two physical DuckDB
schemas that map to Gold and Silver. Bronze never goes into DuckDB; it stays as
Parquet files.

Type `exit()` when done.

---

## Checkpoint

You're done with this module when:
- [ ] You can recite what each layer (Bronze / Silver / Gold) holds and who it serves.
- [ ] `dbt ls --select mart_prices` shows the full lineage back to staging.
- [ ] The Gold query returned `company_name`, `daily_return_pct`, and `ma_50` — columns
      that don't exist in Bronze at all.
- [ ] You can answer: *why doesn't Silver just replace Bronze?* (Hint: immutability.)

---

## Exercises

1. **Trace a different mart.** Run `dbt ls --select mart_fundamentals --output name`.
   How many models does it depend on? Open each `.sql` file and describe in one
   sentence what each one does.
2. **Count the grain.** Bronze prices has 900 rows (3 tickers × 300 days). Run
   `SELECT COUNT(*) FROM main_gold.mart_prices` — it should be the same 900. Then
   run it on `main_silver.int_prices_with_returns`. All three layers have the same
   count because **grain is preserved** from Bronze through Silver to Gold for prices.
   When would grain *change* between layers?
3. **Look at a mart column that doesn't exist in any source.** `daily_return` in
   `mart_prices` is computed from two Bronze rows (today's and yesterday's close). No
   ingestion script produced it. Find where it's calculated: open
   `models/intermediate/int_prices_with_returns.sql` and find the line.

---

## Going deeper (optional)

- The original Medallion blog post from Databricks: search "Databricks Medallion
  architecture" — the pattern is now industry-standard.
- dbt's own take on layers: <https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview>

---

**Next:** Module 04 — Transformation techniques: the interesting SQL inside the
Silver intermediate models — how we normalise messy XBRL tags and compute window
functions (moving averages, returns). Say **"next"** when your checkpoint boxes
are ticked.
