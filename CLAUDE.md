# CLAUDE.md — working context for this repo

End-to-end S&P 500 data-engineering portfolio project. Read this first; it loads
automatically for every Claude Code session here.

## What this project is

A medallion-architecture analytics platform built as a **learning portfolio**:
Bronze (raw Parquet) → Silver (dbt staging/intermediate) → Gold (dbt marts) →
BI (Power BI semantic model + report) → conversational NL Q&A. The owner is learning
each tool hands-on, so **explain *why* before *how*, and call out shell-vs-Python /
local-vs-cloud context switches.**

## Repo map

| Path | What |
|------|------|
| `dbt/sp500_analytics/` | dbt project. Run dbt commands from **here**. |
| `dbt/.../models/marts/` | Gold layer: `dim_tickers` (hub) + `mart_*` facts. |
| `dbt/.../ci/profiles.yml` | dbt profile. `duckdb` (local/CI) + `databricks` (cloud) targets. |
| `ingestion/`, `extraction/` | Public-API ingestion + LLM extraction. Run from repo root. |
| `nl_query/` | Streamlit text-to-SQL app. `ontology.py` = our semantic layer. |
| `dashboards/sp500_Analytics.*` | Power BI **PBIP** project (TMDL + PBIR, diffable). |
| `docs/cloud-setup.md` | Cloud provisioning guide. Part G = NL Q&A architecture. |
| `learn/` | Hands-on curriculum + command/git references (local only; git-ignored). |

## Conventions

- **Branch:** develop on `claude/sp500-data-portfolio-sinj32`. Commit small, push often.
- **dbt:** preamble before any dbt command —
  `DBT_PROFILES_DIR=dbt/sp500_analytics/ci`, plus `DATA_DIR` (duckdb) or the four
  `DATABRICKS_*` vars (databricks). `generate_schema_name` macro keeps clean
  `sp500.silver`/`sp500.gold` names on Databricks; concatenated `main_silver`/`main_gold`
  on DuckDB.
- **PBIP editing:** I write data bindings + positions in `visual.json`; **format/titles
  are done in Power BI Desktop** (writing `vcObjects`/`objects` by hand violates the PBIR
  schema). Power BI rewrites position floats on open — **close it before `git pull`**.
- **Lint:** `ruff check ingestion extraction nl_query scripts` must pass (CI gate).

## NL Q&A / ontology direction

The report is a narrative ending in a "ask it yourself" endpoint. Two layers:
**engine** (what answers) and **surface** (where you type). See `docs/cloud-setup.md`
Part G. Our own ontology lives in `nl_query/ontology.py` (works today); the native
**Fabric IQ Ontology** is generated from the Power BI semantic model when Fabric
capacity lands. Same vocabulary, two implementations.

## Microsoft Fabric knowledge

For Fabric-specific work (REST APIs, T-SQL/KQL, ontology, data agents, Power BI),
Microsoft maintains reusable AI skills at
**https://github.com/microsoft/skills-for-fabric**. To use them:

- **Knowledge (now, no Fabric needed):** clone that repo and run Claude Code from
  inside it — its `CLAUDE.md` auto-loads Fabric expertise. Useful while authoring TMDL,
  planning the ontology, and designing the data agent.
- **Live MCP (needs Fabric capacity + `az login`):** register the Fabric / data-agent
  MCP server so Claude can query live. Config + steps are in `docs/cloud-setup.md`
  Part G. Runs on the laptop, not the cloud build session.

Fabric Data Agents run on **Azure OpenAI GPT** (not Claude); Claude reaches them as a
**tool via the data-agent MCP server**. Copilot is the native surface; Claude-over-MCP
is the alternative surface — both over the same ontology-grounded engine.
