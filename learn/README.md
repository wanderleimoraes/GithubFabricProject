# Learning Lab — Syllabus

This folder turns the project into a **hands-on course**. Each module is one focused
session: read the concept, run the commands, hit the checkpoint, try the exercises.
We do **one module at a time** and don't race ahead.

Every lesson has the same structure:
- **Concept** — what the tool/technique is and *why* it exists (plain language).
- **In this repo** — the exact files where it lives.
- **Hands-on** — commands to run, with expected output.
- **Checkpoint** — how to know it worked.
- **Exercises** — small things to try (and break, and fix).
- **Going deeper** — optional, for later.

## Legend

| Symbol | Meaning |
|--------|---------|
| 💻 **Here** | Runs in this web environment — offline, free, instant feedback. |
| 🌐 **Your machine** | Needs internet, an API key, the cloud, or a paid tool — run it locally / in Azure. |

## Modules

### Foundation — 💻 runs here (offline, synthetic data)
- [x] **[00 — Orientation & setup](00-orientation.md)** — what we're building; install the toolchain; map the repo.
- [x] **[01 — Warehouses & DuckDB](01-warehouses-duckdb.md)** — what a data warehouse is; generate sample data; query it.
- [x] **[02 — dbt fundamentals](02-dbt-fundamentals.md)** — models, `source()`/`ref()`, materializations, compile vs run.
- [x] **[03 — Medallion architecture](03-medallion-architecture.md)** — Bronze / Silver / Gold and why we layer data.
- [x] **[04 — Transformation techniques](04-transformation-techniques.md)** — normalizing messy XBRL; window functions.
- [x] **[05 — Testing & documentation](05-testing-documentation.md)** — dbt tests, docs, and the lineage graph.

### Real data & cloud — 🌐 your machine / Azure
- [x] **[06 — Ingestion & public APIs](06-ingestion-public-apis.md)** — SEC EDGAR, yfinance, rate limits.
- [x] **[07 — LLM extraction technique](07-llm-extraction-technique.md)** — turning text into structured rows with Claude.
- [ ] **[08 — Natural-language Q&A](08-natural-language-qa.md)** — text-to-SQL over the marts.
- [ ] **09 — Cloud lakehouse: Databricks vs Microsoft Fabric** — the lakehouse in the cloud; compare both platforms (the repo is named for Fabric but built on Databricks) and pick one at this cost decision point.
- [ ] **10 — Power BI dashboards** — building the four planned reports.
- [ ] **11 — Orchestration & CI** — scheduling the pipeline; what our CI does.

Check a box as you finish each module. The foundation modules (00–05) need nothing
but this environment; we'll decide on local-vs-cloud when we reach module 06.

## How a session works

1. You open the module file and read the **Concept**.
2. We go through the **Hands-on** together — I explain as you run each command.
3. You confirm the **Checkpoint**, then try the **Exercises** on your own.
4. When you're ready, say **"next"** and we move to the following module.
