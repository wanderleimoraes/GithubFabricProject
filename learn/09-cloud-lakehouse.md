# Module 09 — Cloud Lakehouse: Databricks vs Microsoft Fabric  🌐 your machine

**Goal:** understand what a cloud lakehouse is, how Databricks and Fabric compare,
and decide which one to use before spending any cloud credit.

No commands to run this session — this is the cost-decision point. Read, think,
then decide.

---

## Concept

### From local DuckDB to the cloud

You've been running the entire pipeline on your laptop using DuckDB — a single `.duckdb`
file, no server, no cost. That works perfectly for development and learning. But it has
limits:

- Only one person can write to the file at a time.
- You can't run a scheduled nightly job without leaving your laptop on.
- Power BI can connect, but every refresh copies data out of DuckDB into Power BI's memory.
- There's no governance layer — no audit log of who queried what.

A **cloud lakehouse** solves these problems. The name blends two ideas:
- **Data lake** — store raw and processed files (Parquet, Delta) cheaply in object storage (Azure Blob/ADLS).
- **Data warehouse** — run fast SQL on those files; enforce schemas; serve BI tools.

The key insight: **the files are the source of truth, not the compute.** Spark, SQL, Python,
and Power BI all read the same underlying Parquet/Delta files. You can swap or scale the
compute without migrating data.

---

## The two platforms

### Azure Databricks

Databricks invented **Delta Lake** — the open-source format we use. On Azure it runs on your
own subscription (you control the VMs; Databricks manages the platform).

**What it provides:**
- **Delta Lake** — Parquet files with an ACID transaction log (`_delta_log/`). This is what
  makes lakehouse tables behave like database tables: commits, rollback, time travel.
- **Spark compute** — distributed Python/SQL for transformations. For our 0.6M-row dataset
  this is overkill, but the pattern scales to billions of rows unchanged.
- **SQL Warehouse** — a lightweight cluster optimized for SQL queries (what dbt and Power BI
  connect to). Cheaper than a full Spark cluster for BI workloads.
- **Databricks Jobs** — scheduled runs: trigger `python -m ingestion.*` then `dbt build` on
  a cron, with retry, alerts, and a run history UI.
- **Unity Catalog** — fine-grained access control across all workspaces. Column-level
  masking, row-level security, lineage graph.
- **MLflow** — experiment tracking for ML models (relevant if you later build a price
  prediction model on top of this data).

**What our repo already has for Databricks:**

```yaml
# dbt/sp500_analytics/profiles.yml.example (databricks target)
databricks:
  type: databricks
  catalog: sp500
  schema: gold
  host: "{{ env_var('DATABRICKS_HOST') }}"
  http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
  token: "{{ env_var('DATABRICKS_TOKEN') }}"
```

Those four env vars — `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`,
`DATABRICKS_CATALOG` — are everything dbt needs. The same 22 models, same SQL, same
tests run unchanged on Databricks. The `--target databricks` flag is the only switch.

**Cost model:**
- You pay for **DBUs** (Databricks Units) × the Azure VM underneath.
- A single-node `Standard_DS3_v2` cluster (4 cores, 14 GB RAM) costs roughly $0.30–0.50/hr.
- For this project: run ingestion (~10 min) + `dbt build` (~2 min) daily = under $0.50/day.
- New Azure accounts get **$200 free credit** — enough for several months of daily runs.

---

### Microsoft Fabric

Fabric is Microsoft's all-in-one SaaS analytics platform, launched in 2023. Unlike
Databricks (which you deploy into your own subscription), Fabric is a managed service —
Microsoft runs the infrastructure.

**What it provides:**

| Component | What it does |
|-----------|--------------|
| **OneLake** | One storage account for all data, in Delta Lake format. Think of it as OneDrive for data — everything lands here. |
| **Lakehouse** | Spark + Delta tables on top of OneLake. Looks and feels like Databricks. |
| **Data Pipeline** | Drag-and-drop ETL (like Azure Data Factory). Can also trigger notebooks/Python. |
| **Warehouse** | Fully managed SQL engine — no Spark, pure T-SQL. Easier for SQL developers. |
| **Direct Lake** | Power BI reads Parquet files from OneLake **without importing them**. Dashboards refresh in seconds instead of minutes, and there's no 1 GB dataset limit. |
| **Fabric Copilot** | Natural-language assistant built into every Fabric surface. Ask questions about your data in plain English — similar to what we built in Module 08, but built into the platform. |
| **Fabric IQ / Ontology** | A semantic layer where you define your business entities (Company, Metric, Period) and their relationships. Other Fabric tools — Copilot, reports, APIs — can then reason over the ontology. Think of it as a governed schema the whole organisation shares. |

**The Power BI advantage:**

In standard Databricks → Power BI, every report refresh runs a query against the SQL
Warehouse and imports the results into Power BI's in-memory engine. For 0.6M rows this is
manageable, but for large datasets it's slow and you hit the 1 GB import limit.

With Fabric Direct Lake, Power BI reads the Parquet files directly from OneLake.
There is no import step. Refresh is near-instant. The 1 GB limit disappears. For a
portfolio project where the point is to build Power BI dashboards, this is a significant
difference.

**dbt support:**

Fabric has a `dbt-fabric` adapter (Microsoft-maintained). Our project would need minor
profile changes — same SQL, same tests. The adapter is newer and slightly less mature
than `dbt-databricks`, but it works for our use case.

**Cost model:**
- Fabric is priced by **capacity units** (F-SKUs). The smallest useful tier is F2 (~$0.36/hr
  on pay-as-you-go). You can pause capacity when not in use.
- Microsoft offers a **60-day free trial** of Fabric (F64 capacity) with a Microsoft 365 account.
- After the trial, F2 on pay-as-you-go with careful pausing costs $5–15/month for a
  portfolio project.

---

## Comparison table

| Dimension | Azure Databricks | Microsoft Fabric |
|-----------|-----------------|-----------------|
| **Storage format** | Delta Lake (your ADLS) | OneLake (Delta Lake, managed) |
| **Compute** | Spark + SQL Warehouse | Spark Lakehouse + SQL Warehouse |
| **dbt adapter** | `dbt-databricks` (mature) | `dbt-fabric` (newer) |
| **Power BI integration** | Standard import connector | **Direct Lake** (no import) |
| **Natural language over data** | via external API (Module 08) | Copilot built-in |
| **Semantic ontology** | not built-in | **Fabric IQ / Ontology** |
| **Orchestration** | Databricks Jobs | Data Pipeline + triggers |
| **Governance** | Unity Catalog | Fabric workspace + row-level security |
| **Free entry point** | $200 Azure credit (new accounts) | 60-day trial (any Microsoft 365) |
| **Long-term cost** | pay-per-use DBUs | capacity-based, can pause |
| **Best for** | ML workloads, heavy Spark, multi-cloud | Power BI-first, Microsoft ecosystem |

---

## Can they work together?

Yes. Because both platforms use **Delta Lake** as the on-disk format, the files are
compatible. A common pattern:

1. Databricks runs the Spark transformations and writes Delta tables to ADLS Gen2.
2. Fabric's OneLake **shortcuts** to that same ADLS path — it reads the same Delta files
   without copying them.
3. Power BI uses Direct Lake to serve those tables.

This means you could keep Databricks for heavy compute and add Fabric just for Power BI
and Fabric IQ — they share the same data layer. If you ever decide you want the Ontology
layer on top of this project, you can add Fabric later without re-ingesting anything.

---

## In this repo

- [`dbt/sp500_analytics/profiles.yml.example`](../dbt/sp500_analytics/profiles.yml.example) —
  the two targets (`duckdb` and `databricks`). Adding a third `fabric` target would be a
  one-block addition.
- [`dbt/sp500_analytics/dbt_project.yml`](../dbt/sp500_analytics/dbt_project.yml) —
  the `+schema: silver` / `+schema: gold` directives become catalog schemas in the cloud.
- [`docs/architecture.md`](../docs/architecture.md) — the architecture document that
  describes the Medallion layers; platform-agnostic by design.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — CI always runs on DuckDB;
  cloud targets are for production only.
- [`docs/cloud-setup.md`](../docs/cloud-setup.md) — the click-by-click provisioning
  guide for the chosen Option C architecture (Databricks → Fabric → Direct Lake).

---

## Hands-on (read-only — no cloud spend yet)

### 1. Read the profiles file

Open `dbt/sp500_analytics/profiles.yml.example`. Notice:

- The `duckdb` target uses a relative file path — no server needed.
- The `databricks` target uses four environment variables. Nothing is hardcoded; secrets
  stay out of the repo.
- Switching targets is one flag: `dbt build --target databricks`.

### 2. Understand the schema mapping

In `dbt_project.yml`:
```yaml
models:
  sp500_analytics:
    staging:
      +schema: silver      # → DuckDB: main_silver  |  Databricks: sp500.silver
    marts:
      +schema: gold        # → DuckDB: main_gold    |  Databricks: sp500.gold
```

DuckDB has no catalogs, so `main_silver` is the schema name. Databricks has a three-level
namespace: `catalog.schema.table` → `sp500.silver.stg_market_prices`. The SQL models
themselves don't change — dbt handles the mapping via `{{ ref() }}`.

### 3. Find the four env vars you'd need for Databricks

If you were to provision a Databricks workspace today, the values would come from:
- `DATABRICKS_HOST` — the workspace URL (`adb-<id>.azuredatabricks.net`)
- `DATABRICKS_HTTP_PATH` — the SQL Warehouse's connection path (under Compute → SQL Warehouses → Connection details)
- `DATABRICKS_TOKEN` — a personal access token (User settings → Developer → Access tokens)
- `DATABRICKS_CATALOG` — `sp500` (you'd create this in Unity Catalog)

You'd add these four lines to your `.env` file, then run `dbt build --target databricks` instead of `--target duckdb`. Every model, test, and doc works identically.

---

## The decision

For this project's stated goals:

| Goal | Points to |
|------|-----------|
| Power BI Direct Lake (fast, no import limit) | Fabric |
| Fabric IQ / Ontology integration later | Fabric |
| Current repo already wired for Databricks | Databricks |
| 60-day free trial available now | Fabric |
| $200 Azure credit (new accounts only) | Databricks |
| Mature dbt adapter | Databricks |

**Decision made: Option C — Databricks + Fabric together.** Databricks runs the
compute and writes Delta tables; Fabric reads those same files via a OneLake shortcut
and serves them to Power BI through Direct Lake. This gives both: Databricks for
compute and Unity Catalog governance, Fabric for fast BI and future Fabric IQ /
Ontology work — without copying data, because both use Delta Lake on disk.

> **Step-by-step provisioning:** see [`docs/cloud-setup.md`](../docs/cloud-setup.md).
> It's the click-by-click guide for Databricks → Entra ID user → Fabric → OneLake
> shortcut → Direct Lake, with cost-discipline rules and a teardown checklist.

> **Credit window:** the €200 Azure credit expires **2026-07-24**. The setup guide is
> structured as a ~3-week sprint so the durable artifacts (`.pbix` files, screenshots,
> this repo) are captured before the cloud resources are torn down.

**On the personal-email block:** Microsoft Fabric rejects personal Gmail/Outlook
addresses. Your Azure subscription includes an Entra ID tenant that provides an
organisational `@*.onmicrosoft.com` account Fabric *does* accept — Part B of the
setup guide walks through creating it.

---

## Checkpoint

You're done with this module when:
- [ ] You can explain what Delta Lake is and why both platforms use it.
- [ ] You understand what Direct Lake means and why it matters for Power BI.
- [ ] You know which four env vars are needed to point dbt at Databricks.
- [ ] You've decided which platform to provision first (or to skip cloud for now and
      continue with DuckDB for Power BI via the standard connector).

---

## Exercises

1. **Add a Fabric target.** Open `profiles.yml.example` and add a third target block
   named `fabric` using the `dbt-fabric` adapter fields (look at the
   [dbt-fabric docs](https://docs.getdbt.com/docs/core/connect-data-platform/fabric-setup)).
   Don't fill in real credentials yet — just get the structure right.

2. **Find the catalog in Unity Catalog.** Read
   [Unity Catalog concepts](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
   and identify where the `sp500` catalog name in `profiles.yml.example` would be created.

3. **Estimate the monthly cost.** Assume a nightly run: 10 min ingestion + 2 min dbt build
   on a `Standard_DS3_v2` node at $0.40/hr. How much does that cost per month? How does
   that compare to Fabric F2 at $0.36/hr paused 23.8 hr/day?

---

## Going deeper (optional)

- [Delta Lake documentation](https://docs.delta.io/latest/index.html) — the open-source
  format both platforms use.
- [Microsoft Fabric Direct Lake deep dive](https://learn.microsoft.com/en-us/power-bi/enterprise/directlake-overview) —
  explains exactly how Power BI reads Parquet without import.
- [dbt-databricks adapter docs](https://docs.getdbt.com/docs/core/connect-data-platform/databricks-setup)
- [dbt-fabric adapter docs](https://docs.getdbt.com/docs/core/connect-data-platform/fabric-setup)
- [Fabric IQ overview](https://learn.microsoft.com/en-us/fabric/intelligence/overview) —
  the Copilot + Ontology layer.

---

**Next:** Module 10 — Power BI dashboards. We'll build the four planned reports connecting
to your Gold marts (DuckDB locally, or cloud if you've provisioned it). Say **"next"** when
your checkpoint boxes are ticked.
