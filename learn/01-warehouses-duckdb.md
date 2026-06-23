# Module 01 — Warehouses & DuckDB  💻 runs here

**Goal:** understand what a *data warehouse* is and why analysts use one, then
generate this project's synthetic sample data and run your **first real queries**
against it with DuckDB. By the end you'll have actually seen data move.

---

## Concept

### What is a "data warehouse"?

A **data warehouse** is a database built for **analytics** — answering questions
like *"what was each company's average revenue over 5 years?"* — rather than for
running an app. The difference matters:

- An **application database** (the kind behind a website) is optimised for many tiny
  reads and writes: *"fetch user #42", "save this order"*. One row at a time.
- A **warehouse** is optimised for scanning **millions of rows** to compute sums,
  averages, and trends. Few writes, huge reads.

That single difference drives a different storage design (**columnar** — more below),
and it's why you don't just run analytics on the app's database.

### Columnar storage (the one idea that explains the speed)

Imagine a table of stock prices with columns `ticker, date, open, close, volume`.

- A **row store** keeps each row's fields together on disk:
  `MSFT,2021-01-04,100,101,1M | MSFT,2021-01-05,101,102,1M | ...`
  To average the `close` column it must read **every field of every row**.
- A **column store** keeps each column together:
  all `close` values in one block, all `volume` values in another.
  To average `close`, it reads **only the close block** — skipping everything else.

For analytics (which touch a few columns but many rows), columnar is dramatically
faster and compresses better. **DuckDB and Parquet are both columnar** — that's why
we use them.

### Two tools you meet here

- **Parquet** — a columnar **file format**. Each Bronze dataset in this project is a
  `.parquet` file. It's just a file on disk, but internally organised by column.
- **DuckDB** — a columnar **database engine** that runs *in-process* (no server to
  start, like SQLite but for analytics). It can query Parquet files **directly**,
  without importing them first. That's the superpower we'll use today.

### Where this fits

This is **Stage 2 (Storage)** from Module 00's five stages. Today we use DuckDB as a
free, local stand-in for a cloud warehouse so you can learn all the SQL and dbt
mechanics offline. Later (Module 09) the same models run on Databricks — the concepts
transfer directly.

---

## In this repo

- [`scripts/generate_sample_bronze.py`](../scripts/generate_sample_bronze.py) —
  writes small, **deterministic** synthetic Bronze datasets (same numbers every run,
  via a fixed random seed). This is the data CI uses, and what you'll query today.
- [`ingestion/config.py`](../ingestion/config.py) — defines where data lives:
  `DATA_DIR` (default `./data`) and `BRONZE_DIR` (`./data/bronze`).
- [`dbt/sp500_analytics/models/staging/_sources.yml`](../dbt/sp500_analytics/models/staging/_sources.yml)
  — declares the five Bronze datasets and the exact Parquet paths dbt reads. Open it
  and notice the five `name:` entries — they match the files you're about to create.

The five Bronze datasets:

| Dataset | What it holds |
|---------|---------------|
| `sp500_constituents` | company reference list (ticker, name, sector, CIK) |
| `market_prices` | daily OHLCV stock prices |
| `fundamentals` | financial facts from SEC filings (revenue, net income, …) |
| `filings` | SEC filing metadata (e.g. 8-K) |
| `ai_commitments` | LLM-extracted AI investment commitments |

---

## Hands-on

Make sure your venv is active first — your prompt should show `(.venv)`. If not:
`.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux).

### 1. Generate the sample Bronze data

```bash
python -m scripts.generate_sample_bronze
```
*Expected:* five lines like `wrote   900 rows -> market_prices`, one per dataset.

### 2. See what landed on disk

```bash
# Windows PowerShell:
Get-ChildItem -Recurse data\bronze
# Mac/Linux:
ls -R data/bronze
```
*Expected:* a folder per dataset, each containing one `.parquet` file.

### 3. Query a Parquet file directly with DuckDB

No import step — DuckDB reads the file in place. Run Python:

```bash
python
```
Then, at the `>>>` prompt, paste these one at a time:

```python
import duckdb

# How many price rows, and for which tickers?
duckdb.sql("SELECT ticker, COUNT(*) AS n FROM 'data/bronze/market_prices/market_prices.parquet' GROUP BY ticker").show()

# Peek at the first few rows
duckdb.sql("SELECT * FROM 'data/bronze/market_prices/market_prices.parquet' LIMIT 5").show()

# An actual analytics question: average close price per ticker
duckdb.sql("SELECT ticker, ROUND(AVG(close), 2) AS avg_close FROM 'data/bronze/market_prices/market_prices.parquet' GROUP BY ticker ORDER BY avg_close DESC").show()
```
*Expected:* three tickers (MSFT, NVDA, GOOGL), 300 rows each, and an average-price
table. Type `exit()` to leave Python.

### 4. (Optional) Tables vs. views — the core distinction

In the query above, the Parquet file *is* the data; DuckDB read it on the fly. A
**database** can also store query results two ways, and you'll meet both in dbt next
module:

- A **table** = the result is **computed once and saved** as rows on disk. Fast to
  read later; can go stale if the source changes.
- A **view** = the result is a **saved query**, recomputed every time you read it.
  Always fresh; does the work each time.

dbt builds our staging/intermediate layers as **views** (cheap, always fresh) and our
final marts as **tables** (computed once, fast for dashboards). You'll see exactly
that in Module 02 — just hold the distinction for now.

---

## Checkpoint

You're done with this module when:
- [ ] `python -m scripts.generate_sample_bronze` printed five `wrote … rows` lines.
- [ ] `data/bronze/` contains five subfolders, each with a `.parquet` file.
- [ ] A DuckDB query returned **3 tickers with 300 rows each** for `market_prices`.
- [ ] You can say, in one sentence, why columnar storage is faster for analytics.

---

## Exercises

1. **Different dataset.** Query `data/bronze/fundamentals/fundamentals.parquet`. How
   many rows are there? Which `tag` values appear? (Hint:
   `SELECT DISTINCT tag FROM '…'`.)
2. **A join, by hand.** Write one query that joins `market_prices` to
   `sp500_constituents` on `ticker` and returns `company_name, AVG(close)`. (You can
   reference two Parquet files in the same query — give each a path and an alias.)
3. **Break it.** Point a query at a path that doesn't exist (e.g. a typo in the
   filename). Read the error message. Getting comfortable reading errors is half of
   data engineering.

---

## Going deeper (optional)

- Why DuckDB exists: <https://duckdb.org/why_duckdb>
- The Parquet format in plain terms: <https://parquet.apache.org/docs/overview/>
- Row vs. columnar storage, visualised: <https://www.youtube.com/results?search_query=columnar+storage+explained>

---

**Next:** Module 02 — dbt fundamentals: instead of hand-writing queries against file
paths, you'll let **dbt** manage them — `source()`, `ref()`, and building your first
models. Say **"next"** when your checkpoint boxes are ticked.
