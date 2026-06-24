# Module 04 — Transformation techniques  💻 runs here

**Goal:** look inside the two most interesting Silver models in this project and
understand the SQL patterns they use: **window functions** (computing returns and
moving averages across ordered rows) and **seed-driven tag normalization** (turning
messy XBRL financial data into a clean, consistent schema).

These two patterns appear in almost every serious data engineering project. After this
module you'll be able to read and explain them in an interview.

---

## Concept

### Pattern 1 — Window functions

A **window function** computes a value *across a sliding set of rows* without
collapsing them into one row the way `GROUP BY` does. The window is defined by:

- **`PARTITION BY`** — which rows form a group (like `GROUP BY`, but the rows aren't
  collapsed).
- **`ORDER BY`** — the row ordering within that group.
- **frame clause** — which rows in the ordered group to include (e.g. "the 50 rows
  ending at the current row").

The key signature is the `OVER (...)` clause: any aggregate with an `OVER` is a
window function.

Three window functions in this project:

```sql
-- Daily return: today's close relative to yesterday's
adj_close / NULLIF(LAG(adj_close) OVER w, 0) - 1   AS daily_return

-- 50-day moving average: mean of the 50 rows ending here
AVG(adj_close) OVER (
    PARTITION BY ticker ORDER BY trade_date
    ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
)   AS ma_50

-- 200-day moving average
AVG(adj_close) OVER (
    PARTITION BY ticker ORDER BY trade_date
    ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
)   AS ma_200
```

`LAG(x) OVER w` — returns the value of `x` from the *previous* row in the window.
`NULLIF(x, 0)` — guards against dividing by zero (returns NULL if x is 0).
`ROWS BETWEEN N PRECEDING AND CURRENT ROW` — a sliding frame of N+1 rows.

Because these use `PARTITION BY ticker`, each ticker's window is independent — MSFT's
50-day MA never mixes GOOGL's prices in.

### Pattern 2 — Seed-driven tag normalization

EDGAR (the SEC's financial database) stores numbers as **XBRL tags** — XML labels
assigned by each company. The same concept (revenue) can be tagged dozens of ways:

- `Revenues`
- `RevenueFromContractWithCustomerExcludingAssessedTax`
- `SalesRevenueNet`

If you compare "revenue" across companies without normalizing the tags first, you're
comparing apples and oranges. The solution:

1. **A seed CSV** (`seeds/gaap_tag_mapping.csv`) that maps known raw tags to canonical
   metric names.
2. **An `INNER JOIN`** between the raw data and that mapping — only rows with a
   recognized tag survive.
3. **A deduplication step** using `ROW_NUMBER()` — if the same (ticker, period,
   metric) was filed more than once (amendments happen), keep only the most recent
   filing.

This combination — seed lookup + row_number dedup — is a standard data-engineering
pattern for cleaning any source where the same fact can appear under multiple names
and multiple times.

### Why a seed, not hard-coded SQL?

A dbt **seed** is a small CSV file under `seeds/` that dbt loads into the database
as a table. Keeping the mapping in a CSV rather than a `CASE WHEN` block in SQL means:

- A business analyst can update the mapping without touching SQL.
- It's version-controlled and auditable.
- You can add a new tag with one CSV row and `dbt seed` — no SQL refactoring needed.

---

## In this repo

- [`models/intermediate/int_prices_with_returns.sql`](../dbt/sp500_analytics/models/intermediate/int_prices_with_returns.sql)
  — the window-function model. Three derived columns: `daily_return`, `ma_50`,
  `ma_200`. Read it alongside this lesson.
- [`models/intermediate/int_fundamentals_normalized.sql`](../dbt/sp500_analytics/models/intermediate/int_fundamentals_normalized.sql)
  — the tag-normalization model. Four CTEs: `facts`, `mapping`, `mapped`, `deduped`.
- [`seeds/gaap_tag_mapping.csv`](../dbt/sp500_analytics/seeds/gaap_tag_mapping.csv)
  — 12 rows: raw XBRL tag → canonical metric name.
- [`models/marts/mart_fundamentals.sql`](../dbt/sp500_analytics/models/marts/mart_fundamentals.sql)
  — pivots the normalized long table into a wide table (one column per metric per
  row), then adds `net_margin` and `rnd_intensity` as derived ratios.

---

## Hands-on

Make sure you're in the dbt project folder with env vars set:

```powershell
cd C:\dev\GithubFabricProject\dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
```

### 1. Read the window-function model in full

Open `models/intermediate/int_prices_with_returns.sql` in VS Code. It's 27 lines.
Read every line. Then:

```python
import duckdb
con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")

# See the window-function results for one ticker
con.sql("""
    SELECT trade_date,
           ROUND(close, 2)          AS close,
           ROUND(daily_return*100, 3) AS return_pct,
           ROUND(ma_50, 2)          AS ma_50,
           ROUND(ma_200, 2)         AS ma_200
    FROM main_silver.int_prices_with_returns
    WHERE ticker = 'MSFT'
    ORDER BY trade_date
    LIMIT 10
""").show()
```

*What to notice:* `return_pct` is NULL on row 1 (no prior day). `ma_50` on row 1
equals `close` (only one row in the window). By row 50 it's a true 50-day average.
By row 200 the `ma_200` is also a full rolling average.

### 2. See the raw fundamentals before normalization

```python
# Raw Bronze: messy long format, raw XBRL tags
duckdb.sql("""
    SELECT ticker, tag, value, fiscal_year
    FROM 'C:/dev/GithubFabricProject/data/bronze/fundamentals/fundamentals.parquet'
    WHERE ticker = 'MSFT'
    ORDER BY fiscal_year, tag
""").show()
```

*What to notice:* many rows per company per year. Each `tag` is a raw XBRL name.
Some of these tags appear in the seed CSV; some don't (and won't survive the join).

### 3. See the normalized fundamentals after the seed join + dedup

```python
# Silver: only recognized tags, deduplicated, canonical metric name
con.sql("""
    SELECT ticker, canonical_metric, value, fiscal_year
    FROM main_silver.int_fundamentals_normalized
    WHERE ticker = 'MSFT'
    ORDER BY fiscal_year, canonical_metric
""").show()
```

*What to notice:* only the rows whose `tag` was in `gaap_tag_mapping.csv` survived.
The tag column is gone; `canonical_metric` is now clean and consistent across all
companies.

### 4. See the final pivoted Gold table

```python
# Gold: one row per (ticker, fiscal_year), metrics as columns
con.sql("""
    SELECT company_name, fiscal_year,
           revenue / 1e9      AS revenue_bn,
           net_income / 1e9   AS net_income_bn,
           ROUND(net_margin * 100, 1) AS net_margin_pct,
           ROUND(rnd_intensity * 100, 1) AS rnd_pct_of_revenue
    FROM main_gold.mart_fundamentals
    ORDER BY fiscal_year, company_name
""").show()
```

*What to notice:* `net_margin` and `rnd_intensity` are computed in `mart_fundamentals.sql`
from the normalized values — they don't exist in Bronze at all. The pivot (long → wide)
happened in the same mart. This is the shape a dashboard or a machine-learning model
wants: one row per entity per period, one column per metric.

Type `exit()` when done.

---

## Checkpoint

You're done with this module when:
- [ ] You can explain `PARTITION BY` and `ROWS BETWEEN` in your own words.
- [ ] You can say why `LAG()` returns NULL on the first row for each ticker.
- [ ] You can describe the three steps in the tag-normalization pipeline (seed join →
      filter → row_number dedup).
- [ ] The Gold fundamentals query returned `net_margin_pct` and `rnd_pct_of_revenue`
      for both fiscal years.

---

## Exercises

1. **Extend the window.** In `int_prices_with_returns.sql`, the moving averages are
   50 and 200 days. What would a 10-day MA look like? Write the SQL fragment (you
   don't have to add it to the model — just write it out).
2. **Add a tag to the seed.** Open `seeds/gaap_tag_mapping.csv`. Add a new row:
   `OperatingIncomeLoss,operating_income`. Run `dbt seed` then query
   `main_silver.int_fundamentals_normalized` — does `operating_income` appear?
   (Spoiler: it won't, because the synthetic data doesn't include that tag. But this
   is exactly how you'd extend the mapping for real data.)
3. **Trace the pivot.** Open `mart_fundamentals.sql` and find the `CASE WHEN`
   expressions. How does SQL turn a long table (many rows per ticker per year) into
   a wide table (one row per ticker per year)? Write a one-sentence explanation.

---

## Going deeper (optional)

- Window functions, exhaustive reference: <https://duckdb.org/docs/sql/window_functions>
- EDGAR XBRL tags: the SEC's full taxonomy lives at
  <https://xbrl.fasb.org/us-gaap/> — useful to understand why normalizing is hard.
- dbt seeds: <https://docs.getdbt.com/docs/build/seeds>

---

**Next:** Module 05 — Testing & documentation: how the 8 tests in `dbt build` work,
writing a custom singular test, and generating the lineage graph with `dbt docs`.
Say **"next"** when your checkpoint boxes are ticked.
