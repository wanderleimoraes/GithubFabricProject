# Module 02 — dbt fundamentals  💻 runs here

**Goal:** stop hand-writing queries against file paths and let **dbt** manage them.
You'll learn what a dbt *model* is, how `source()` and `ref()` wire models together,
what "materialization" means, and the difference between `compile`, `run`, and
`build`. Then you'll run `dbt build` and watch it construct every table in the right
order — automatically.

---

## Concept

### The problem dbt solves

In Module 01 you wrote a join with **hardcoded file paths**, table aliases, and a
specific order things had to happen in. That's fine for one query. But a real project
has dozens of queries where each depends on the output of others. Managing by hand:
*which runs first? what breaks if I rename a column? where is this table even used?*

**dbt (data build tool)** solves this. You write each transformation as a plain
`SELECT` statement in a `.sql` file (a **model**). dbt figures out the dependencies,
runs everything in the correct order, and creates the tables/views for you. You never
write `CREATE TABLE` — you just describe *what the data should look like*, and dbt
handles the *how*.

### The three ideas that make dbt click

**1. A model is a SELECT.** Each `.sql` file under `models/` contains one `SELECT`.
dbt wraps it in `CREATE TABLE AS` or `CREATE VIEW AS` for you and names the result
after the file. `stg_market_prices.sql` → a relation called `stg_market_prices`.

**2. `source()` and `ref()` replace hardcoded names.** Instead of writing a raw file
path or table name, you reference things symbolically:

- `{{ source('bronze', 'market_prices') }}` — "the raw Bronze market_prices input."
  Defined once in `_sources.yml`; dbt expands it to the real path.
- `{{ ref('stg_market_prices') }}` — "the output of the stg_market_prices model."

These two functions are how dbt **learns the dependency graph**. Because model B says
`ref('A')`, dbt knows A must be built before B. You never specify run order manually —
the `ref()`s *are* the order.

**3. Materialization = how the result is stored.** Each model is built as either:
- a **view** (a saved query, recomputed on read — cheap, always fresh), or
- a **table** (computed once and stored — costs storage, fast to read).

You set this in `dbt_project.yml`, not in the SQL. In our project, staging and
intermediate are **views**, marts are **tables** (see below).

### compile vs run vs build (three verbs you'll use constantly)

- **`dbt compile`** — turns your templated SQL (the `{{ ref() }}` stuff) into real SQL
  and writes it to `target/`, but **runs nothing**. Great for *seeing* what dbt will
  execute.
- **`dbt run`** — actually executes the models, creating the views/tables.
- **`dbt build`** — `run` + `test` + `seed` + `snapshot`, all in dependency order.
  This is the "do everything correctly" command we'll lean on.

---

## In this repo

- [`dbt/sp500_analytics/dbt_project.yml`](../dbt/sp500_analytics/dbt_project.yml) —
  the project config. Note the `models:` block: `staging` and `intermediate` are
  `+materialized: view`, `marts` are `+materialized: table`. That's where the
  view-vs-table decision lives — *not* in the SQL.
- [`models/staging/_sources.yml`](../dbt/sp500_analytics/models/staging/_sources.yml)
  — declares the five Bronze inputs that `source()` resolves to.
- [`models/staging/stg_market_prices.sql`](../dbt/sp500_analytics/models/staging/stg_market_prices.sql)
  — a textbook staging model: it reads `{{ source('bronze', 'market_prices') }}`,
  casts each column to a clean type, and drops null-close rows. Nothing fancy —
  staging models just **clean and standardize**, one per raw input.
- [`dbt/sp500_analytics/ci/profiles.yml`](../dbt/sp500_analytics/ci/profiles.yml) —
  the **profile**: tells dbt *which database to connect to*. Ours points the
  `duckdb` target at a single local file, `${DATA_DIR}/sp500.duckdb`.

The six staging models (`stg_constituents`, `stg_market_prices`, `stg_fundamentals`,
`stg_filings`, `stg_ai_events`, `stg_ai_commitments`) each clean one source.

### A note on the profile (important for running locally)

dbt keeps *project logic* (the models) separate from *connection details* (the
profile). The profile lives outside the project by default (in `~/.dbt/`), but you
can point dbt at our committed `ci/profiles.yml` with the `DBT_PROFILES_DIR`
environment variable. We'll do exactly that below.

---

## Hands-on

All commands run from inside the dbt project folder, with the venv active.

### 1. Move into the dbt project and point dbt at the config

PowerShell (Windows) — use **your** absolute repo path:

```powershell
cd C:\dev\GithubFabricProject\dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
```

(Mac/Linux equivalent: `export DATA_DIR=/path/to/repo/data` and
`export DBT_PROFILES_DIR=/path/to/repo/dbt/sp500_analytics/ci`.)

Setting `DATA_DIR` to an **absolute** path matters: it makes both the Bronze Parquet
inputs *and* the output DuckDB file resolve to the same `data/` folder you populated
in Module 01.

### 2. Check the connection

```bash
dbt debug
```
*Expected:* a series of checks ending in `All checks passed!`. If the connection or
profile is wrong, this is where you find out — before running any models.

### 3. See dbt's dependency graph as compiled SQL (run nothing yet)

```bash
dbt compile --select stg_market_prices
```
Then open `target/compiled/sp500_analytics/models/staging/stg_market_prices.sql` in
VS Code. Notice the `{{ source(...) }}` has been replaced with a real Parquet path —
that's the templating doing its job.

### 4. Load the seeds, then build everything

```bash
dbt seed
dbt build
```
*Expected:* dbt builds the staging views, intermediate views, mart tables, loads
seeds, and runs tests — all in dependency order. The final summary should read
something like `PASS=22 WARN=0 ERROR=0 SKIP=0`.

### 5. Query a dbt-built model (compare to Module 01)

```bash
python -c "import duckdb; con=duckdb.connect('C:/dev/GithubFabricProject/data/sp500.duckdb'); con.sql('SELECT ticker, ROUND(AVG(close),2) AS avg_close FROM silver.stg_market_prices GROUP BY ticker').show()"
```
*Expected:* the same averages as Module 01 — but now you queried a **named model in a
schema** (`silver.stg_market_prices`), not a raw file path. That's the upgrade dbt
gives you: stable names instead of brittle paths.

---

## Checkpoint

You're done with this module when:
- [ ] `dbt debug` ends with `All checks passed!`.
- [ ] `dbt build` finishes with `ERROR=0` (something like `PASS=22`).
- [ ] You opened a compiled file in `target/compiled/…` and saw `source()` expanded
      into a real path.
- [ ] You can explain, in one sentence each, what `source()` and `ref()` do.

---

## Exercises

1. **Read another staging model.** Open `models/staging/stg_fundamentals.sql`. What
   source does it read? What cleaning does it do? (Compare its shape to
   `stg_market_prices.sql`.)
2. **Selective runs.** Run `dbt run --select staging` — only the staging models build.
   Then `dbt run --select stg_market_prices+` (note the trailing `+`): that builds
   `stg_market_prices` *and everything downstream of it*. The `+` is dbt's
   graph-selection syntax — very handy on big projects.
3. **Break a `ref` and read the error.** Temporarily misspell a `ref()` in any model
   (e.g. `ref('stg_market_pricez')`), run `dbt compile`, and read how dbt reports the
   broken dependency. **Undo it afterward** (`git checkout <file>`).

---

## Going deeper (optional)

- dbt models, in their words: <https://docs.getdbt.com/docs/build/models>
- `source()` and `ref()`: <https://docs.getdbt.com/reference/dbt-jinja-functions/ref>
- Materializations: <https://docs.getdbt.com/docs/build/materializations>

---

**Next:** Module 03 — Medallion architecture: *why* the models are split into
staging → intermediate → marts (the Bronze/Silver/Gold pattern), and what belongs in
each layer. Say **"next"** when your checkpoint boxes are ticked.
