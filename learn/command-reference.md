# Command Reference — Why, Where, and What Each Command Does

This file explains every command used in the learning modules. For each one:
- **What it does** — the plain-language purpose
- **Why here** — why it runs in the shell vs Python, and why from a specific folder
- **What goes wrong** — the most common mistake

---

## The two contexts: Shell vs Python

Before anything else — the most important distinction:

| Context | Prompt looks like | Used for |
|---------|-------------------|----------|
| **PowerShell (shell)** | `PS C:\dev\...>` | Running programs, installing packages, git, dbt |
| **Python interactive** | `>>>` | Writing Python code line by line, querying data |

You **cannot** run `python -m something` inside `>>>`. You **cannot** run `import duckdb` in PowerShell. If you get an error like "import is not recognized", you're in the wrong context.

---

## One-time setup (Module 00)

### `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
**Shell — run once ever**

Windows blocks PowerShell scripts by default for security. This command unlocks
them for your user account only (`-Scope CurrentUser`). Without it, activating
the virtual environment fails with "running scripts is disabled."

### `py -3.12 -m venv .venv`
**Shell — run once per project, from the repo root**

Creates a `.venv` folder containing an isolated Python 3.12 installation. "Virtual
environment" means packages you install here don't interfere with other projects.
Must be Python 3.12 specifically — Python 3.14 breaks dbt-core (mashumaro
incompatibility).

### `.venv\Scripts\activate`
**Shell — run every time you open a new terminal window**

"Activates" the virtual environment. After this, `python` and `pip` point to
`.venv\Scripts\python.exe` instead of your system Python. You know it's active
when `(.venv)` appears at the start of your prompt.

**What goes wrong:** Forgetting to activate — then `import dbt` fails because
dbt isn't installed in the system Python.

### `pip install -r requirements.txt`
**Shell — run once after creating the venv, or after `requirements.txt` changes**

Reads `requirements.txt` and installs every listed package into the active venv.
`pip` is the Python package installer; `-r` means "from a file."

---

## Configuration (Module 00 / 06)

### `Copy-Item .env.example .env`
**Shell — run once**

`.env.example` is the template committed to git (safe to share). `.env` is your
private copy with real API keys and paths. The `.gitignore` file prevents `.env`
from being committed. If you skip this step, scripts can't find your API keys or
data directory.

### `$env:DATA_DIR = "C:\dev\GithubFabricProject\data"`
### `$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"`
**Shell — run every time before using dbt**

These set **environment variables** — named values the operating system passes to
programs. dbt reads `DATA_DIR` to find the DuckDB database and Parquet files;
`DBT_PROFILES_DIR` tells dbt where its connection config (`profiles.yml`) lives.

**Why not permanent?** You could add them to your PowerShell profile, but for now
we set them manually each session so you know exactly what's happening.

**What goes wrong:** Forgetting these before `dbt build` → dbt can't find the
database and fails with a path error.

---

## Generating sample data (Module 01)

### `python -m scripts.generate_sample_bronze`
**Shell — from the repo root**

`python -m module.name` tells Python "find the module at `scripts/generate_sample_bronze.py`
and run it." The `-m` flag is how you run a Python file as a module (respects
package imports). Running `python scripts/generate_sample_bronze.py` directly
sometimes breaks relative imports.

Creates 5 synthetic Parquet files in `data/bronze/` with fake but realistic
S&P 500 data (3 companies, 300 days) for offline testing. Replaces real data
from ingestion if you've already run that.

---

## Ingestion commands (Module 06)

All ingestion commands run **from the repo root** in the shell, not from inside
the `dbt/` folder.

### `python -m ingestion.sp500_constituents`
**Shell — run first, before any other ingestion**

Fetches the S&P 500 company list from Wikipedia and maps each ticker to its
SEC CIK number (the SEC's internal company ID). Every other ingestion script
reads this file to know which companies to fetch. If you run `market_prices`
before this, it builds the constituent list on the fly — slower and less
reliable.

### `python -m ingestion.market_prices [--limit N]`
**Shell**

Downloads 5 years of daily OHLCV prices from Yahoo Finance via the `yfinance`
library. `--limit N` restricts to the first N tickers — use `--limit 5` to
test before committing to all 503 (~2 minutes). No API key needed.

### `python -m ingestion.edgar_fundamentals [--limit N]`
**Shell**

Calls the SEC EDGAR `companyfacts` API for each company and downloads all
XBRL financial facts. SEC enforces a 10 req/sec rate limit; the script sleeps
0.12 seconds between requests. Full run takes ~10 minutes for 503 companies.
No API key needed, but the `SEC_USER_AGENT` in `.env` is required.

### `python -m ingestion.edgar_filings [--limit N]`
**Shell**

Fetches 8-K filing metadata (not the full documents) from the SEC `submissions`
API. Writes a table of filings with URLs pointing to the actual HTML documents.
The LLM extractor downloads those documents on demand. Full run takes ~10 minutes.

---

## LLM extraction (Module 07)

### `python -m extraction.ai_commitment_extractor [--limit N]`
**Shell — from repo root, requires ANTHROPIC_API_KEY in .env**

Reads `filings.parquet`, sorts by most-recent date, takes the first N filings,
downloads each HTML document from SEC archives, strips the HTML to plain text,
sends it to Claude with a structured extraction prompt, and writes any AI
investment commitments found to `ai_commitments.parquet`.

Default `--limit` is 25. Start small (5–25) to confirm it works before running
larger batches (API costs ~$0.01 per filing).

**What goes wrong:** Running without the full `edgar_filings` dataset means only
a few companies are in the file — likely none with AI commitments. Always run
`edgar_filings` without `--limit` first.

### `python -m extraction.ai_material_facts_extractor [--limit N]`
**Shell — from repo root, requires ANTHROPIC_API_KEY in .env**

Broader sibling of the commitment extractor. Reads `filings.parquet`, downloads each
8-K, and asks Claude to extract **any material AI fact** (partnerships, products,
infrastructure capex, acquisitions, research, revenue/demand, governance,
risk/regulatory) — not just quantified dollar commitments. Each row is rich and
**source-linked** (verbatim `fact_text`, `context`, `filing_item`, `accession_number`,
`source_url`) so a reader can click through to the filing and judge for themselves.
Writes `ai_material_facts.parquet`, modeled as `mart_ai_material_facts`.

Default `--limit` is 25. Costs ~$0.01–0.02 per filing (a bit more than the commitment
extractor because the prompt returns more per filing).

---

## dbt commands (Modules 02–05)

All dbt commands run **from `dbt/sp500_analytics/`** — that's where `dbt_project.yml`
lives. dbt refuses to run from any other folder.

```powershell
cd dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
```

Those three lines are the **standard preamble** before any dbt command.

### `dbt debug --target duckdb`
Checks that dbt can connect to DuckDB and find all config files. Run this first
if anything seems wrong. "All checks passed" = you're ready.

### `dbt seed --target duckdb`
Loads the CSV files in `seeds/` into DuckDB as tables. Must run before `dbt build`
if the seeds have changed. Seeds are small reference tables that don't come from
ingestion (e.g., `gaap_tag_mapping.csv`).

### `dbt compile --target duckdb`
Converts Jinja SQL (`{{ ref('stg_market_prices') }}`) into plain SQL and writes
the result to `target/compiled/`. **Does not run anything** — useful for
debugging what SQL dbt will actually execute.

### `dbt run --target duckdb`
Builds all models (creates/replaces views and tables in DuckDB). Does NOT run
tests.

### `dbt build --target duckdb`
Runs seeds + models + tests in dependency order. **This is the command you use
most.** If a test fails, the models that depend on it are skipped.

### `dbt test --target duckdb`
Runs only the tests against whatever is already in DuckDB — doesn't rebuild
models first. Faster for checking data quality without a full rebuild.

### `dbt test --select model_name --target duckdb`
Runs tests for one specific model only. Useful when you've changed one model and
want to test just that part. Replace `model_name` with e.g. `mart_prices` or
`assert_mart_fundamentals_grain`.

### `dbt ls --select +mart_prices --output name`
Lists the full dependency chain of a model. The `+` prefix means "include all
ancestors." Without `+`, it only lists the model itself and its direct tests.

### `dbt source freshness --target duckdb`
Checks whether the Bronze source data was loaded recently, based on the
`_ingested_at` column and the thresholds in `_sources.yml`. "Warn" means the
data is older than 48 hours; "Error" means older than 7 days.

### `dbt docs generate --target duckdb`
Reads all model YAML files and builds a JSON catalogue in `target/catalog.json`.
Does not open a browser.

### `dbt docs serve`
Starts a local web server (usually at `http://localhost:8080`) to browse the
catalogue and lineage graph. Press `Ctrl+C` to stop it.

---

## Python interactive queries (Modules 01, 03–05)

These run **inside** the Python prompt (`>>>`), started by typing `python` in the
shell.

### `import duckdb`
Loads the DuckDB library. Must be the first line before any database operations.
`import` is Python's way of loading external libraries that were installed via pip.

### `con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")`
Opens the DuckDB database file and creates a connection object named `con`. All
subsequent queries run through `con`. Use forward slashes (`/`) even on Windows
inside Python strings.

### `con.sql("SELECT ...").show()`
Runs a SQL query against the open database and prints the result as a table.
`.show()` formats the output nicely in the terminal. Without `.show()` the result
object is returned but not printed.

### `duckdb.sql("SELECT ... FROM 'file.parquet'")`
Queries a Parquet file **directly**, without going through DuckDB's named tables.
Note: `duckdb.sql()` (no connection) uses a temporary in-memory database — it
cannot see the `main_silver` or `main_gold` schemas that dbt created. For those,
use `con.sql()` with an open connection to `sp500.duckdb`.

### `exit()`
Exits the Python interactive prompt and returns to the shell. You can also press
`Ctrl+Z` then Enter on Windows.

---

## Natural-language Q&A app (Module 08)

### `streamlit run nl_query/app.py`
**Shell — from the repo root, requires ANTHROPIC_API_KEY in .env**

Starts the text-to-SQL Streamlit app. Streamlit is a web framework — it launches its
own web server and serves a browser UI. A browser tab opens automatically at
`http://localhost:8501`.

**Why `streamlit run` and not `python nl_query/app.py`?**
`python` would run the file once and exit. `streamlit run` keeps the server running,
handles hot-reload when you edit the file, and provides the layout engine (columns,
expanders, charts). The two commands are different entry points for different purposes.

**What goes wrong:** Running from inside `nl_query/` instead of the repo root — the
app uses relative paths to find `dbt/sp500_analytics/target/catalog.json`, so it
must be launched from the project root. Also: forgetting to run `dbt docs generate
--target duckdb` first means `catalog.json` is missing and the app falls back to a
static schema description (still works, but the LLM won't know your exact column names
and descriptions).

Press `Ctrl+C` in PowerShell to stop the app when done.

---

## Power BI data export (Module 10)

### `python -m scripts.export_marts_csv`
**Shell — from the repo root**

Connects to the local DuckDB warehouse, reads all four Gold mart tables, and writes
them as CSV files to `data/export/`. Use this to refresh the local Power BI data
source after running `dbt build --target duckdb`.

**What goes wrong:** Running without first building the dbt models means the Gold
tables don't exist yet → run `dbt build --target duckdb` first.

---

## Cloud platform setup (Module 09)

Module 09 is a read-only decision module — no new shell commands. When you're ready
to provision the cloud platform, the commands below will apply.

### `dbt build --target databricks`
**Shell — from `dbt\sp500_analytics\`, after setting four env vars**

Runs the full dbt pipeline against Azure Databricks instead of DuckDB. Requires:
- `DATABRICKS_HOST` — workspace URL
- `DATABRICKS_HTTP_PATH` — SQL Warehouse connection path
- `DATABRICKS_TOKEN` — personal access token
- `DATABRICKS_CATALOG` — Unity Catalog catalog name (e.g. `sp500`)

The `--target databricks` flag is the only difference from the local workflow. Every
model, test, and seed runs identically.

### `dbt build --target fabric`
**Shell — from `dbt\sp500_analytics\`, after adding a fabric profile block**

Same as above but for Microsoft Fabric. Requires the `dbt-fabric` adapter and a
corresponding target block in `profiles.yml`.

---

## CI & orchestration (Module 11)

### `ruff check ingestion extraction nl_query scripts`
**Shell — from the repo root**

Runs the Python linter across all application code. This is exactly what CI runs on
every push. Catches unused imports, undefined variables, and style issues before they
become runtime errors. Fix any warnings before committing — a clean lint check is
part of the CI green bar.

---

## git commands

> For the full picture — the 4-box model (working dir → staging → local repo → remote),
> branches, conflicts, the daily routine, and how Bitbucket/GitLab compare — see the
> dedicated [Git Guide](git-guide.md). The entries below are the quick reference.

### `git status`
Shows which files have been modified, added, or deleted compared to the last
commit. Run this before pulling to understand your local state.

### `git pull origin claude/sp500-data-portfolio-sinj32`
Downloads the latest commits from GitHub and merges them into your local branch.
This is how you get changes that were pushed from the cloud environment. If the
same file was changed in both places, git will flag a **conflict** — it won't
silently overwrite your work.

### `git log --oneline -5`
Shows the last 5 commits as one line each. Useful for confirming a pull worked —
the most recent commit should match what was pushed from the cloud.

---

## Quick-reference: which folder do I run this from?

| Command | Run from |
|---------|----------|
| `pip install` | anywhere (venv active) |
| `python -m scripts.*` | repo root (`C:\dev\GithubFabricProject`) |
| `python -m ingestion.*` | repo root |
| `python -m extraction.*` | repo root |
| `streamlit run nl_query/app.py` | repo root |
| `dbt *` | `dbt\sp500_analytics\` |
| `git *` | repo root (or anywhere inside the repo) |
| `python` (interactive) | anywhere |
