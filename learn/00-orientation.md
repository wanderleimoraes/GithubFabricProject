# Module 00 — Orientation & Setup  💻 runs here

**Goal:** understand what this project *is* at a high level, get the toolchain
installed, and learn your way around the repository. No data engineering yet — this
is the "lay of the land" module.

---

## Concept

### What are we building?

A **data pipeline**: a system that takes raw data from the outside world, cleans and
reshapes it, and turns it into something people (and dashboards, and AI) can actually
use. Ours is about **S&P 500 companies and the AI boom**.

Think of it as a kitchen:
- **Raw ingredients** = public data (stock prices, company financial filings).
- **Prep & cooking** = transformations that clean and combine the data.
- **Plated dishes** = dashboards and a question-answering assistant.

### The five stages (the "end to end")

1. **Ingestion** — pull raw data in (Python scripts). *Raw ingredients arrive.*
2. **Storage** — keep it in a warehouse/lakehouse. *The pantry and fridge.*
3. **Transformation** — clean and model it with **dbt**. *Prep and cooking.*
4. **Serving** — dashboards (Power BI) + a natural-language Q&A app. *Plating.*
5. **Orchestration & CI** — automate and quality-check the whole thing. *The kitchen's routine and health inspection.*

You don't need to understand any of these deeply yet. Each gets its own module.

### Two key tools you'll meet first

- **dbt** ("data build tool") — lets you transform data by writing **SELECT
  statements**, while it handles the order things run in, testing, and documentation.
  It's the heart of stage 3.
- **DuckDB** — a tiny, free database that runs as a single file on your computer. We
  use it as a practice "warehouse" so you can learn everything offline and for free,
  before touching the cloud.

---

## In this repo

Here's the map. You'll visit each area in later modules.

```
GithubFabricProject/
├── README.md            ← project overview + architecture diagram (read this)
├── docs/architecture.md ← the detailed design (we cover it in modules 03–04)
├── ingestion/           ← STAGE 1: Python scripts that pull raw data   (module 06)
├── scripts/             ← helper: generates fake sample data for practice (module 01)
├── dbt/sp500_analytics/ ← STAGE 3: the dbt project (transformations)   (modules 02–05)
│   ├── models/          ←   the SQL transformations, in layers
│   ├── seeds/           ←   small hand-maintained CSV lookup tables
│   └── tests/           ←   data quality checks
├── extraction/          ← the LLM step (text → structured data)        (module 07)
├── nl_query/            ← STAGE 4a: natural-language Q&A app            (module 08)
├── dashboards/          ← STAGE 4b: Power BI notes                      (module 10)
├── .github/workflows/   ← STAGE 5: CI (automated checks)               (module 11)
└── learn/               ← you are here: the course
```

---

## Hands-on

Run these one at a time. After each, read what came back before moving on.

### 1. Confirm where you are

```bash
pwd
ls
```
*Expected:* you're in the project root and see `README.md`, `dbt/`, `ingestion/`, etc.

### 2. Set up an isolated Python environment

A **virtual environment** ("venv") is a private sandbox for this project's Python
packages, so they don't clash with anything else on your system.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```
*Expected:* your prompt now shows `(.venv)` at the front.

### 3. Install the project's tools

```bash
pip install -r requirements.txt
```
*Expected:* a lot of output ending without errors. This installs dbt, DuckDB,
pandas, and more. (First time can take a couple of minutes.)

### 4. Confirm the two key tools are present

```bash
dbt --version
python -c "import duckdb; print('duckdb', duckdb.__version__)"
```
*Expected:* dbt prints a Core version (1.7+), and DuckDB prints a version number.

---

## Checkpoint

You're done with this module when:
- [ ] Your shell shows `(.venv)` (the environment is active).
- [ ] `dbt --version` prints a version without error.
- [ ] `python -c "import duckdb; ..."` prints a DuckDB version.
- [ ] You can point to where, in the repo tree above, each of the five pipeline
      stages lives.

---

## Exercises

1. Open `README.md` and find the **architecture diagram**. Trace one arrow from a
   data source all the way to a dashboard. You won't understand every box — just get
   a feel for the flow.
2. In `dbt/sp500_analytics/models/`, list the three subfolders. (We'll learn what
   `staging`, `intermediate`, and `marts` mean in modules 02–03 — for now just notice
   they exist.)
3. Why do we use a **virtual environment** instead of just `pip install`-ing globally?
   Write yourself a one-sentence answer; we'll confirm it next session.

---

## Going deeper (optional)

- dbt in one paragraph: <https://docs.getdbt.com/docs/introduction>
- Why DuckDB is great for learning: <https://duckdb.org/why_duckdb>

---

**Next:** Module 01 — Warehouses & DuckDB: we'll generate sample data and run your
first real queries. Say **"next"** when your checkpoint boxes are ticked.
