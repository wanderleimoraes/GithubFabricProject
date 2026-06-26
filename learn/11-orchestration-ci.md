# Module 11 — Orchestration & CI  💻 Here + 🌐 your machine

**Goal:** understand what our GitHub Actions CI does and why, then learn how to
schedule the full pipeline to run nightly without touching it.

---

## Concept

### The two problems

You've built a pipeline that works when you run it manually:

```
ingestion → dbt build → dbt docs generate → export_marts_csv
```

Two problems remain:

1. **It only runs when you remember to run it.** Data goes stale. Yesterday's prices
   aren't in the warehouse until you run ingestion again.
2. **Every code change is untested until you catch a bug.** If someone edits a SQL
   model and breaks the grain test, you won't know until the dashboard shows wrong numbers.

**Orchestration** solves problem 1: a scheduler runs the pipeline automatically on a
cadence (nightly, hourly, etc.).

**CI (Continuous Integration)** solves problem 2: every time code is pushed to GitHub,
an automated workflow runs the test suite and tells you if anything broke.

---

### What CI is (and what it isn't)

CI means: every push to the repo triggers an automated build + test. If it passes, you
know the code is in a working state. If it fails, you get an email before the bug reaches
production.

**What CI is NOT:** it's not deployment. CI checks that the code is correct; a separate
step (CD — Continuous Deployment) would push it to production. For this portfolio project,
CI is enough — you deploy manually when you're ready.

---

## In this repo: `.github/workflows/ci.yml`

Every push or pull request triggers this workflow on GitHub's free Linux runners:

```yaml
jobs:
  lint-and-build:
    steps:
      - Install Python 3.11 + pip install -r requirements.txt
      - ruff check ingestion extraction nl_query scripts   # lint
      - python -m scripts.generate_sample_bronze           # synthetic Bronze
      - dbt seed --target duckdb                           # load seeds
      - dbt build --target duckdb                          # 22 models + tests
      - dbt docs generate --target duckdb                  # catalog.json
```

**Why synthetic Bronze, not real data?**
Real ingestion calls SEC EDGAR, Wikipedia, and yfinance — all external services that
can be slow, rate-limited, or unavailable. If CI depended on them, a 403 from Wikipedia
would fail your build even though your code is correct. Synthetic Bronze makes CI
reproducible and independent of the internet. The real data pipeline runs separately
on your machine or in a scheduled job.

**Why `dbt build` and not just `dbt run`?**
`dbt build` runs seeds + models + tests in dependency order. If the grain test fails,
the downstream models are skipped. This catches data quality regressions, not just
syntax errors.

**Why `dbt docs generate` in CI?**
It confirms the catalog can be built from the current models — which the NL Q&A app
depends on. If a model rename broke the catalog, CI would catch it.

**Why ruff?**
`ruff` is a fast Python linter. It catches unused imports, undefined variables, and
style issues before they become runtime errors. One command, zero config needed (uses
`pyproject.toml` or sensible defaults).

---

## The full pipeline (orchestrated)

When running on a schedule, the steps run in order with a dependency check at each stage:

```
1. ingestion
   ├── python -m ingestion.sp500_constituents      (once/week — list rarely changes)
   ├── python -m ingestion.market_prices           (daily — yesterday's prices)
   ├── python -m ingestion.edgar_fundamentals      (weekly — quarterly filings)
   └── python -m ingestion.edgar_filings           (daily — new 8-K filings)

2. LLM extraction (optional, costs money)
   └── python -m extraction.ai_commitment_extractor --limit 50

3. dbt
   ├── dbt seed --target databricks
   └── dbt build --target databricks              (models + tests)

4. docs
   └── dbt docs generate --target databricks

5. export (only needed for local Power BI; not needed with Fabric Direct Lake)
   └── python -m scripts.export_marts_csv
```

Steps 3–5 only run if step 1 succeeds. This is what an orchestrator enforces.

---

## Scheduling options

### Option A — GitHub Actions scheduled workflow (simplest, free)

GitHub Actions supports cron schedules. Add this to `ci.yml` to run the real ingestion
nightly (not just synthetic):

```yaml
on:
  schedule:
    - cron: '0 6 * * *'   # 6 AM UTC every day
  push:
    branches: ["**"]
```

Then add your secrets in **GitHub → Settings → Secrets and variables → Actions**:
- `ANTHROPIC_API_KEY`
- `SEC_USER_AGENT`
- `DATABRICKS_HOST` (when ready)
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN`

The workflow reads them via `${{ secrets.ANTHROPIC_API_KEY }}`.

**Limitation:** GitHub's free tier gives 2,000 minutes/month for private repos (unlimited
for public). A full ingestion run takes ~15 minutes, so ~130 nightly runs fit in the free
tier — enough for this project.

### Option B — Databricks Jobs (production path)

When you've provisioned Databricks, create a Job in the UI:

1. **Cluster:** single-node `Standard_DS3_v2`, auto-terminate after 20 minutes.
2. **Tasks (in order):**
   - Task 1: Python script — `ingestion/market_prices.py`
   - Task 2: Python script — `ingestion/edgar_filings.py` (depends on Task 1)
   - Task 3: dbt task — `dbt build --target databricks` (depends on Task 2)
3. **Schedule:** daily at 6 AM UTC.
4. **Alerts:** email on failure.

Databricks Jobs handle retries, dependency ordering, and failure notifications natively.
Cost: ~$0.15 for a 15-minute run on a small cluster.

### Option C — Windows Task Scheduler (local, for testing)

If you want nightly runs from your laptop without GitHub or Databricks:

1. Create `scripts/run_pipeline.ps1`:
```powershell
cd C:\dev\GithubFabricProject
.venv\Scripts\activate
python -m ingestion.market_prices
cd dbt\sp500_analytics
dbt build --target duckdb
```

2. Open Task Scheduler → Create Task → Triggers → Daily at 6 AM → Action: run the `.ps1`.

This is fragile (laptop must be on, VPN etc.) — use it only while you're setting up. Move
to GitHub Actions or Databricks Jobs for anything reliable.

---

## Hands-on

### 1. Read the CI workflow

Open `.github/workflows/ci.yml`. Find the answer to each of these:
- What Python version does CI use? (hint: not the same as your local machine)
- Which folder does `dbt build` run from? How does the workflow handle that?
- What environment variables does CI set, and where do their values come from?

### 2. Watch a CI run

Go to the repo on GitHub → **Actions** tab. Click the latest run. Open
`lint-and-build` → expand each step. You'll see:
- How long `pip install` takes (~30s with cache, ~90s without)
- The `dbt build` output you know from local runs
- The `PASS=22` line that confirms the test suite is green

### 3. Add the scheduled trigger (optional)

If you want nightly ingestion via GitHub Actions, open `.github/workflows/ci.yml`
and replace the `on:` block:

```yaml
on:
  schedule:
    - cron: '0 6 * * *'
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]
```

Then add your secrets in the GitHub repo settings. The workflow will need a separate
job for real ingestion (since the current job only uses synthetic data).

---

## Checkpoint

- [ ] You can explain what CI does and why it uses synthetic Bronze instead of real data.
- [ ] You understand the difference between the CI job (test correctness) and the
      orchestration job (run the real pipeline on a schedule).
- [ ] You know where to add GitHub secrets for the scheduled workflow.
- [ ] You can read `.github/workflows/ci.yml` and describe what each step does.

---

## Exercises

1. **Find the cache.** In the CI workflow, `actions/setup-python` has a `cache: pip`
   option. Look at two CI runs — one where it says "Cache hit" and one where it says
   "Cache miss". How much time does the cache save?

2. **Add a lint check locally.** Run `ruff check ingestion extraction nl_query scripts`
   from the repo root. If there are warnings, fix one. This is exactly what CI runs.

3. **Estimate the monthly CI cost.** The repo is public (GitHub Actions is free for
   public repos). If it were private, how many minutes per month would a push-on-every-
   commit workflow use, assuming 2 pushes per day and 5 minutes per run?

---

## Going deeper (optional)

- [GitHub Actions docs](https://docs.github.com/en/actions) — the full reference for
  workflow syntax, secrets, and caching.
- [Databricks Jobs docs](https://docs.databricks.com/en/workflows/jobs/jobs.html) —
  how to wire multi-task pipelines with dependencies and retries.
- [dbt Cloud](https://docs.getdbt.com/docs/dbt-cloud/dbt-cloud-introduction) — if you
  want a managed scheduler specifically for dbt (has a free tier). Handles
  `dbt build` scheduling without Databricks Jobs.
- [ruff docs](https://docs.astral.sh/ruff/) — the linter we use. Much faster than
  flake8 or pylint; written in Rust.

---

## You've completed the curriculum

Here's what you built across these eleven modules:

| Layer | What you built |
|-------|---------------|
| **Bronze** | Raw ingestion from SEC EDGAR, yfinance, Wikipedia |
| **Silver** | dbt staging + intermediate models: typed, cleaned, deduplicated |
| **Gold** | Four mart tables: prices, fundamentals, AI commitments, AI events |
| **LLM layer** | Structured extraction of AI commitments from 8-K filings |
| **NL Q&A** | Text-to-SQL Streamlit app over the Gold marts |
| **Dashboards** | Four Power BI reports connecting to the marts |
| **Cloud** | Databricks → ADLS Gen2 → Fabric Direct Lake pipeline (Option C) |
| **CI** | GitHub Actions: lint + synthetic Bronze + dbt build + docs on every push |

The patterns here — Medallion architecture, dbt layering, LLM extraction, text-to-SQL,
Direct Lake — are exactly what appears in job descriptions for senior data engineers.
You've built them from scratch and can explain every line.

Pull the latest and commit your `.pbix` files to `dashboards/` when they're ready.
Then update the root `README.md` with screenshots — that's the portfolio showcase.
