# Module 05 — Testing & documentation  💻 runs here

**Goal:** understand the two kinds of dbt tests, see how the YAML schema file
doubles as documentation, and generate the lineage graph that shows every model's
dependencies in a browser.

---

## Concept

### Why test a data pipeline at all?

SQL models are easy to break silently. A bad join can multiply rows; a missing
`WHERE rn = 1` can silently include duplicates; a renamed column in staging can
propagate NULLs all the way to the Gold mart — and a dashboard just shows zero
instead of crashing. Unit tests don't help here because the bug is in the *data
shape*, not in code logic.

dbt's answer is **data tests**: SQL assertions that run against the materialised
tables and views after every build.

### Generic tests (schema tests)

Declared in YAML files (`_marts.yml`, `_sources.yml`). Four built-in flavours:

| Test | What it checks |
|------|----------------|
| `not_null` | No NULL values in a column |
| `unique` | Every value in a column appears only once |
| `accepted_values` | All values are in an allowed list |
| `relationships` | Every foreign-key value exists in the referenced table |

In this project's `_marts.yml`:

```yaml
- name: ticker
  data_tests: [not_null]
```

That single line generates a SQL query like:

```sql
SELECT COUNT(*) FROM main_gold.mart_prices WHERE ticker IS NULL
```

If the count is non-zero, the test fails and `dbt build` reports an error.

### Singular tests (custom SQL assertions)

For anything the four built-ins can't express, you write a SQL file in `tests/`.
The contract is simple: **return rows on failure, return zero rows on success.**

This project has one singular test:
`tests/assert_mart_fundamentals_grain.sql`:

```sql
-- Returns offending rows; the test passes when zero rows are returned.
SELECT ticker, period_end, COUNT(*) AS n_rows
FROM {{ ref('mart_fundamentals') }}
GROUP BY ticker, period_end
HAVING COUNT(*) > 1
```

It checks **grain**: the (ticker, period_end) combination must be unique — one row
per company per fiscal period. If a deduplication bug crept in, this catches it.

The `ref()` inside a test works exactly like in a model — dbt resolves it to the
real table name, so the test always runs against the currently-built mart.

### dbt YAML as documentation

The same `_marts.yml` that declares tests also holds **descriptions** for every
model and column. This is important for two reasons:

1. `dbt docs generate` reads these descriptions and builds a browsable data
   catalogue with a **lineage graph** — you can click any model and see all its
   upstream dependencies and downstream consumers.
2. The catalogue is what the **NL Q&A layer** (Module 08) reads as schema context
   before generating SQL. Good descriptions = better AI-generated queries.

---

## In this repo

- [`models/marts/_marts.yml`](../dbt/sp500_analytics/models/marts/_marts.yml)
  — schema + tests for all four Gold marts. 7 `not_null` tests declared here.
- [`tests/assert_mart_fundamentals_grain.sql`](../dbt/sp500_analytics/tests/assert_mart_fundamentals_grain.sql)
  — the singular grain test. 1 test file = 1 assertion.
- [`models/staging/_sources.yml`](../dbt/sp500_analytics/models/staging/_sources.yml)
  — declares the Bronze Parquet files as dbt sources (with freshness thresholds).

Total: 8 tests across the project (7 generic + 1 singular), all run by `dbt build`.

---

## Hands-on

Make sure you're in the dbt project folder with env vars set (from Module 02):

```powershell
cd C:\dev\GithubFabricProject\dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
```

### 1. Run just the tests (without rebuilding models)

```powershell
dbt test --target duckdb
```

You should see something like:

```
22:14:01  Running with dbt=1.x.x
22:14:01  Found 10 models, 8 tests, ...
22:14:02  Finished running 8 tests in 0.xx seconds.
22:14:02  8 of 8 PASS
```

*What to notice:* `dbt test` runs only the tests against whatever is already in
DuckDB — it doesn't rebuild models first. `dbt build` does both (models then tests).

### 2. See a failing test

Open `models/marts/_marts.yml`. Under `mart_prices`, add a `unique` test to
`trade_date`:

```yaml
      - name: trade_date
        data_tests: [not_null, unique]
```

Save the file, then run:

```powershell
dbt test --select mart_prices --target duckdb
```

This will **fail** — `trade_date` is not unique (every ticker has the same
dates). Read the error message: dbt tells you exactly which test failed and how
many rows violated the constraint.

**Undo the change** (remove `unique` from `trade_date`) before moving on — the
test is intentionally wrong.

### 3. Add a valid new test

Under `mart_prices`, the `adj_close` column has no test. Add one:

```yaml
      - name: adj_close
        description: "Dividend/split-adjusted close price."
        data_tests: [not_null]
```

Save and run:

```powershell
dbt test --select mart_prices --target duckdb
```

The new test should pass. This is how you extend coverage: one line in YAML.

**Revert** by removing the `data_tests: [not_null]` line from `adj_close`.

### 4. Read the singular test

Open `tests/assert_mart_fundamentals_grain.sql`. Notice:

- It uses `ref('mart_fundamentals')` — the same function used in models.
- It `GROUP BY ticker, period_end` and `HAVING COUNT(*) > 1` — it returns
  *duplicate* rows if any exist.
- Zero rows returned = test passes. Any rows returned = test fails.

Run it standalone (note the `--select` flag uses the test file name without `.sql`):

```powershell
dbt test --select assert_mart_fundamentals_grain --target duckdb
```

Should pass — our synthetic data has no duplicates.

### 5. Generate and browse the lineage graph

```powershell
dbt docs generate --target duckdb
dbt docs serve
```

`dbt docs generate` writes a catalogue to `target/catalog.json`. `dbt docs serve`
starts a local web server (usually at `http://localhost:8080`).

Open that URL in a browser. Click **"Lineage Graph"** (bottom right). You'll see
every model as a node — click `mart_fundamentals` and trace the arrows back to
`stg_fundamentals` → `int_fundamentals_normalized` → `mart_fundamentals`. That
visual is the entire dependency chain we've been building.

Click a model node and look at the **"Columns"** tab — the descriptions from the
YAML file appear there. This is the living documentation that stays in sync with
the code.

Press `Ctrl+C` in PowerShell to stop the docs server when done.

---

## Checkpoint

You're done with this module when:
- [ ] `dbt test --target duckdb` shows all 8 tests passing.
- [ ] You added a failing `unique` test to `trade_date`, saw dbt report the
      failure, then reverted it.
- [ ] You can describe the difference between a generic test and a singular test
      in one sentence each.
- [ ] The lineage graph opened in a browser and you traced `mart_fundamentals`
      back to its Bronze source.

---

## Exercises

1. **Write your own singular test.** Create
   `tests/assert_prices_no_future_dates.sql`. It should return rows where
   `trade_date > CURRENT_DATE`. Run it with
   `dbt test --select assert_prices_no_future_dates --target duckdb`. It should
   pass (synthetic dates are in 2021–2022).
2. **Add a description to a column.** In `_marts.yml`, add a description to
   `mart_prices.close`. Run `dbt docs generate --target duckdb` and check that
   the new description appears in the browser catalogue.
3. **Break the grain test.** In a Python prompt, run:
   ```python
   import duckdb
   con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")
   con.sql("INSERT INTO main_gold.mart_fundamentals SELECT * FROM main_gold.mart_fundamentals LIMIT 1").fetchall()
   ```
   Then run `dbt test --select assert_mart_fundamentals_grain --target duckdb`.
   It should fail. Run `dbt build --target duckdb` afterwards to rebuild the
   table from scratch and restore the clean state.

---

## Going deeper (optional)

- Full list of built-in generic tests and how to write custom ones:
  <https://docs.getdbt.com/docs/build/data-tests>
- dbt docs and the catalogue schema: <https://docs.getdbt.com/reference/commands/cmd-docs>
- The lineage graph uses a format called a **DAG** (Directed Acyclic Graph) —
  every data pipeline tool (Airflow, Prefect, Dagster) uses the same concept.

---

**Next:** Module 06 — Ingestion & public APIs: this is where we leave the offline
sandbox and connect to the real world. You'll need your local machine for this one
(SEC EDGAR, yfinance, an API key). Say **"next"** when your checkpoint boxes
are ticked.
