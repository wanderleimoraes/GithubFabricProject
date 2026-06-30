# Cloud Setup Guide — Azure Databricks → Fabric → Direct Lake (Option C)

This is the click-by-click guide to stand up the cloud pipeline using your Azure
credit. It assumes you've completed the local modules (00–11) and have a working
dbt project that builds against DuckDB.

> **⏱️ Credit window:** the €200 Azure credit expires **2026-07-24**. This guide is
> written as a ~3-week sprint. The Azure resources are temporary; the durable
> portfolio artifacts (`.pbix` files, screenshots, this repo) are what you keep.
> **Tear everything down before the expiry date** (see Part F).

> **⚠️ UI drift:** Azure and Fabric portals change their labels often. If a button
> name here doesn't match exactly, look for the nearest equivalent — the *concepts*
> (workspace, SQL warehouse, catalog, shortcut, semantic model) are stable.

---

## Prerequisites

- An Azure subscription with credit (you have this).
- Power BI Desktop installed locally (Module 10).
- This repo cloned locally with a working `.venv` and `dbt build --target duckdb` passing.
- Your `.env` file with `ANTHROPIC_API_KEY` and `SEC_USER_AGENT`.

---

## Cost discipline (read first)

Two rules prevent accidental credit drain:

1. **Auto-terminate Databricks compute.** Always set clusters/warehouses to stop after
   10–20 minutes idle. An idle cluster left running overnight is the #1 way people
   burn credit.
2. **Pause Fabric capacity when not building.** Fabric F2 bills per hour while
   *active*. Pause it from the Azure portal the moment you stop working; resume when
   you come back.

Estimated spend for this whole sprint if disciplined: **€20–30** of your €200.

---

## Part A — Azure Databricks

**Goal:** a Databricks workspace with a SQL Warehouse, so `dbt build --target databricks`
writes your Gold marts to Unity Catalog.

### A1. Create the workspace

1. [Azure Portal](https://portal.azure.com) → **Create a resource** → search
   **Azure Databricks** → **Create**.
2. Fields:
   - **Resource group:** create new, name it `rg-sp500`.
   - **Workspace name:** `sp500-databricks`.
   - **Region:** pick one close to you (e.g. `West Europe`).
   - **Pricing tier:** **Premium** (required for Unity Catalog).
3. **Review + create** → **Create**. Wait ~5 minutes for deployment.
4. When done → **Go to resource** → **Launch Workspace**.

### A2. Confirm Unity Catalog + create a catalog

Premium workspaces get a Unity Catalog metastore auto-attached in most regions.

1. In the Databricks workspace, left sidebar → **Catalog**.
2. Click **Create catalog** → name it `sp500` → **Create**.
   - If "Create catalog" is greyed out, the metastore isn't attached. Go to the
     [Databricks Account Console](https://accounts.azuredatabricks.net) → **Catalog** →
     create a metastore for your region, then assign it to the workspace.
3. Inside `sp500`, create two schemas: **silver** and **gold** (Create schema button).

> These map to dbt's `+schema: silver` / `+schema: gold` settings. The catalog name
> `sp500` matches `DATABRICKS_CATALOG` in `profiles.yml.example`.

### A3. Create a SQL Warehouse

1. Left sidebar → **SQL Warehouses** → **Create SQL Warehouse**.
2. Fields:
   - **Name:** `sp500-wh`.
   - **Cluster size:** **2X-Small** (smallest — plenty for our data).
   - **Auto stop:** **10 minutes** ← critical for cost.
3. **Create** → wait for it to start.
4. Click the warehouse → **Connection details** tab. **Copy these two values:**
   - **Server hostname** → this is your `DATABRICKS_HOST`.
   - **HTTP path** → this is your `DATABRICKS_HTTP_PATH`.

### A4. Create a personal access token

1. Top-right → your username → **Settings** → **Developer** → **Access tokens** →
   **Manage** → **Generate new token**.
2. Comment: `dbt`. Lifetime: 30 days (covers the credit window).
3. **Copy the token immediately** — it's shown once. This is `DATABRICKS_TOKEN`.

### A5. Wire dbt to Databricks

1. Add the four values to your local `.env`:
   ```
   DATABRICKS_HOST=adb-xxxxxxxxxxxx.azuredatabricks.net
   DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxxxxxxxxx
   DATABRICKS_TOKEN=dapi...
   DATABRICKS_CATALOG=sp500
   ```
2. Make sure `~/.dbt/profiles.yml` (or `DBT_PROFILES_DIR`) has the `databricks` target
   from `profiles.yml.example`. It reads those four env vars.

### A6. Load Bronze data and build

The cloud warehouse is empty. You need Bronze data there first. Two options:

- **Simplest for a portfolio:** upload your local Bronze Parquet to a Databricks volume
  or use the Databricks UI to import the files, then point `_sources.yml` at them.
- **Cleaner:** run ingestion locally (writes Parquet), then use `databricks fs cp` (the
  Databricks CLI) to copy `data/bronze/` into a Unity Catalog volume.

Then build:
```powershell
# PowerShell — from dbt\sp500_analytics
$env:DATABRICKS_HOST = "..."        # or rely on .env via your shell
dbt build --target databricks
```

**✅ Checkpoint + artifact:** in Databricks → **Catalog** → `sp500` → `gold`, you see
`dim_tickers`, `mart_prices`, `mart_fundamentals`, `mart_ai_commitments`,
`mart_ai_events`, `mart_ai_material_facts`.
**Screenshot this** → save to `dashboards/cloud_unity_catalog.png`.

### A6b. Loading one Bronze table (the concrete recipe)

The Bronze tables were created by uploading each Parquet to a Unity Catalog **volume**
and running `CREATE TABLE … AS SELECT` over it in the SQL Editor. Use this same recipe
whenever you add a **new** Bronze source (e.g. `ai_material_facts`):

1. **Upload the file.** Databricks → **Catalog** → `sp500` → `bronze` → **Volumes** →
   `raw` → **Upload** → pick
   `data/bronze/ai_material_facts/ai_material_facts.parquet`.
2. **Create the Delta table** (SQL Editor):
   ```sql
   CREATE OR REPLACE TABLE sp500.bronze.ai_material_facts AS
   SELECT * FROM parquet.`/Volumes/sp500/bronze/raw/ai_material_facts.parquet`;
   ```
3. **Rebuild** so the new mart appears:
   ```powershell
   dbt build --target databricks --select +mart_ai_material_facts
   ```

> **Timestamp note:** the nanosecond-timestamp fix (`scripts/convert_bronze_timestamps.py`)
> is only needed for files with `_ingested_at` (prices, fundamentals, filings).
> `ai_material_facts` has only date columns, so it loads as-is.

---

## Part B — Entra ID user for Fabric (fixes the personal-email block)

Fabric rejects personal Gmail/Outlook. Your Azure subscription includes an Entra ID
tenant that gives you an organisational `@*.onmicrosoft.com` account Fabric accepts.

### B1. Find your tenant domain

1. Azure Portal → search **Microsoft Entra ID** → **Overview**.
2. Note the **Primary domain** — looks like `yourname.onmicrosoft.com`.

### B2. Create a user

1. Entra ID → **Users** → **New user** → **Create new user**.
2. Fields:
   - **User principal name:** `fabricadmin` → full address `fabricadmin@yourname.onmicrosoft.com`.
   - **Display name:** `Fabric Admin`.
   - Set a password (note it down).
3. **Create**.

### B3. Give it the rights it needs

1. Still in Entra ID → **Roles and administrators** → assign **Global Administrator**
   (or at least the rights to manage Fabric) to `fabricadmin` for simplicity in a
   sandbox tenant.
2. Sign out of Azure, sign back in as `fabricadmin@yourname.onmicrosoft.com` to verify
   the account works and set a permanent password if prompted.

> **This is the email you'll use for Fabric** — not your Gmail.

---

## Part C — Microsoft Fabric

### C1. Provision Fabric capacity (bills against Azure credit)

1. Azure Portal → **Create a resource** → search **Microsoft Fabric** → **Create**.
2. Fields:
   - **Resource group:** `rg-sp500`.
   - **Capacity name:** `sp500fabric`.
   - **Region:** **Sweden Central** *(see region note below)*.
   - **Size:** **F2** (smallest).
   - **Fabric capacity administrator:** select `fabricadmin@...`.
3. **Review + create** → **Create**.

> **Region decision (what actually happened).** West Europe — the region hosting the
> Databricks workspace — would have co-located Fabric with the Delta files. But West
> Europe Fabric quota for a new subscription was **0**, and **both** a support ticket
> *and* a self-service quota request to raise it to 2 were **declined** (West Europe is
> a capacity-constrained region for new subscriptions). Several other EU regions already
> showed a standing quota of 4 CU, so Fabric F2 was provisioned in **Sweden Central**
> instead. The OneLake shortcut (Part C4) therefore reads the West Europe Delta files
> **cross-region** — a negligible first-load latency / tiny egress cost for a
> portfolio-size model, and a clean talking point: *compute region decoupled from
> storage region over the same OneLake shortcut.* Databricks stays in West Europe; only
> the Fabric capacity is in Sweden Central.

> F2 bills ~€0.30/hr while running. **Pause it** (Azure Portal → the capacity resource
> → **Pause**) whenever you're not actively building.

> **Sizing decision — request F2, not F64.** This is a single-user portfolio with a
> small Direct Lake model; **F2 (2 CU) is sufficient.** Early capacity flows surface
> **F64** by default (it's the enterprise headline tier, and Copilot historically
> enforced an F64 minimum), so "64" can end up on a quota ticket even though it isn't
> needed. A large ask in a constrained region triggers heavy capacity-team review;
> **F2 is the fast, near-automatic approval.** If F64 appears on a request, correct it
> to F2. Caveat: a few Copilot features may still enforce an F64 floor, but the
> **Fabric data agent + ontology** (our actual goal) run on low SKUs.
>
> **If West Europe quota is unavailable:** the whole platform is reproducible from
> dbt, so you can redeploy Databricks to an alternate region (e.g. **Sweden Central**,
> **Poland Central**) and request F2 there instead. With the credit expiring
> 2026-07-24, speed beats co-location — take whichever region grants F2 first.
> (When filing a quota request, include your Azure **subscription ID** and the
> support **SR number** — keep those in your ticket, not in the public repo.)

### C2. Create a Fabric workspace

1. Go to [app.fabric.microsoft.com](https://app.fabric.microsoft.com), sign in as
   `fabricadmin@...`.
2. **Workspaces** → **New workspace** → name `sp500-analytics`.
3. **Advanced** → **License mode** → **Fabric capacity** → select `sp500fabric`.
4. **Apply**.

### C3. Create a Lakehouse

1. In the workspace → **New item** → **Lakehouse** → name `sp500_lakehouse` → **Create**.

### C4. OneLake shortcut to the Databricks Delta files

This is the heart of Option C — Fabric reads the *same* Delta files Databricks wrote,
no copy.

1. In the Lakehouse, under **Tables** → **…** (or **New shortcut**) → **New shortcut**.
2. Choose **Azure Data Lake Storage Gen2** (the storage backing Unity Catalog) —
   *or*, if your region supports it, the **Azure Databricks Unity Catalog** shortcut
   type directly.
3. Provide the connection:
   - **URL:** the ADLS Gen2 endpoint backing your `sp500.gold` schema (find it in
     Databricks → Catalog → `sp500` → `gold` → a table → **Details** → Storage location).
   - **Authentication:** organizational account or account key.
4. Select the `gold` folder / mart tables → **Create**.

**✅ Checkpoint + artifact:** the four mart tables appear under **Tables** in the
Lakehouse, marked as shortcuts. **Screenshot** → `dashboards/cloud_onelake_shortcut.png`.

---

## Part D — Direct Lake semantic model + Power BI

### D1. Create the Direct Lake semantic model

1. In the Lakehouse → **New semantic model** (or **New Power BI semantic model**).
2. Select the four mart tables → **Confirm**.
3. Fabric creates a **Direct Lake** model — it reads Parquet directly, no import, no
   refresh schedule needed.
4. In the model editor, add the **relationships** (fact marts → `dim_tickers` on
   `ticker`) and the **DAX measures** already defined in the PBIP semantic model
   under `dashboards/sp500_Analytics.SemanticModel/`.

### D2. Connect Power BI Desktop

1. Power BI Desktop → **Get Data** → **Power BI semantic models** → sign in as
   `fabricadmin@...` → select the `sp500-analytics` model.
2. Build the four report pages (Module 10, Step 5). Because the data is live via
   Direct Lake, no refresh step is needed — it reflects the latest `dbt build`.

### D3. Publish (optional)

**Publish** from Power BI Desktop → select the `sp500-analytics` workspace. The report
is now viewable in the Fabric service.

**✅ Checkpoint + artifact:** all four reports render. **Screenshot each page** →
`dashboards/report*.png`. **Save the `.pbix`** → `dashboards/sp500_analytics.pbix`.
Commit all of it. *This is the portfolio payload.*

---

## Part E — Capture proof (do this before teardown)

The cloud resources vanish after July 24; these artifacts are permanent. Make sure
each is committed to git **before** Part F:

- [ ] `dashboards/cloud_unity_catalog.png` — Databricks Gold tables
- [ ] `dashboards/cloud_onelake_shortcut.png` — Fabric shortcut
- [ ] `dashboards/report1_fundamentals.png` … `report4_nlqa.png`
- [ ] `dashboards/sp500_analytics.pbix`
- [ ] Update root `README.md` with the best screenshot and a line:
      *"Built and verified end-to-end on Azure Databricks + Microsoft Fabric (Direct Lake)."*
- [ ] Update [`docs/architecture.md`](architecture.md) §8 cost summary with your actual spend.

---

## Part G — Conversational NL Q&A: the report's destination

The report is a **narrative**: pages 1–3 tell the story (fundamentals → AI commitments
→ price & events), and the final page hands the reader the keys — a place where *they*
ask their own questions in plain language. This section is the blueprint for that
endpoint. Most of it is gated on Fabric capacity (the pending support ticket), so it's
documented here and built when the capacity lands.

### The two layers (don't conflate them)

An "ask it yourself" experience has two separable layers:

| Layer | What it is | Options |
|-------|-----------|---------|
| **Engine** | The brain that understands the data and answers | Fabric Data Agent (GPT) grounded on an **Ontology**, *or* a custom Claude text-to-SQL app |
| **Surface** | Where the user types the question | **Copilot** in Power BI (native), *or* **Claude** via MCP, *or* the Streamlit chat box |

The engine and surface are independent — the same ontology-grounded engine can be reached
from multiple surfaces.

### The ontology (Fabric IQ)

[Fabric IQ Ontology](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview) (Preview)
is Microsoft's semantic layer: it models **entity types** (Company, Commitment, Filing),
**properties**, and **relationships** ("Company *files* an 8-K"), then **binds** them to
data in OneLake. Crucially, you can
[**generate an ontology from a Power BI semantic model**](https://learn.microsoft.com/en-us/fabric/iq/ontology/concepts-generate) —
so our existing star schema (`dim_tickers` + four marts), relationships, and DAX measures
become the seed. The ontology is what lets the agent answer *complex* questions
(multi-table, comparative, temporal) reliably instead of guessing joins.

### The engine: Fabric Data Agent

A [Fabric Data Agent](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)
runs on **Azure OpenAI GPT models hosted in Fabric** (currently `gpt-5.1` / `gpt-5-mini`) —
*not* Claude. Copilot in Power BI is the same GPT lineage. The agent reasons over the
ontology to answer questions grounded in our defined entities and relationships.

### Reaching it with Claude (via MCP)

The data agent can be published as an
[**MCP server**](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-mcp-server)
(Preview). That makes the GPT-powered, ontology-grounded agent a **tool** that *Claude*
(Claude Code / Claude Desktop / our own app) can call. So a user asks Claude → Claude calls
the Fabric data agent → the agent reasons over the ontology → returns a grounded answer.
This is the more impressive engineering story: *"I exposed my Fabric data agent over MCP
and drove it with Claude."*

### Using `microsoft/skills-for-fabric` in our favour

[`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric) is two
things in one repo — treat them separately:

1. **Skills + `CLAUDE.md` (knowledge — works today, no Fabric needed).** Reusable AI
   instructions for Fabric (REST API patterns, T-SQL/KQL, medallion design, Power BI
   workflows). When Claude Code runs inside the cloned repo, its `CLAUDE.md` loads
   automatically, giving Claude expert Fabric context. Use this **now** while we author
   TMDL, plan the ontology, and design the agent — it makes Claude a better Fabric builder
   at zero cost.

   ```bash
   git clone https://github.com/microsoft/skills-for-fabric.git
   # then run Claude Code from inside that folder for Fabric-specific work,
   # or copy its CLAUDE.md / relevant skills into this project as reference.
   ```

2. **Live MCP wiring (action — needs Fabric capacity + `az login`).** Connects Claude to a
   live Fabric MCP server (REST APIs, or the data-agent MCP server) for real queries.

   ```bash
   az login
   az account get-access-token --resource https://api.fabric.microsoft.com
   ```

   Then register the Fabric MCP server (bearer-token pattern in the client's `mcp.json`):

   ```json
   {
     "mcpServers": {
       "fabric": {
         "url": "https://<your-fabric-mcp-server>",
         "transport": "http",
         "auth": { "type": "bearer", "token": "${FABRIC_MCP_TOKEN}" }
       }
     }
   }
   ```

   > Note: this wiring runs on **your laptop** (it needs `az login` and network access to
   > your Fabric workspace), not the cloud build session.

### Build sequence

| Phase | State | Endpoint |
|-------|-------|----------|
| **Now** | No Fabric capacity | Streamlit text-to-SQL app (Claude engine, runs against Databricks). 4th report page = launchpad (Smart Narrative recap + link to the live app). |
| **When Fabric lands** | F2 capacity active | Mirror `sp500` catalog → generate **Ontology** from the semantic model → stand up a **Fabric Data Agent** → reach it via **Copilot** (native) *and* **Claude over MCP**. 4th page repoints to the native experience. |

The narrative is unchanged across phases: pages 1–3 tell the story, page 4 hands over the
keys. Only the engine behind the keys gets upgraded.

---

## Part F — Teardown checklist (before 2026-07-24)

Delete in this order to stop all billing. Even with credit, leaving resources up past
expiry can incur real charges.

1. **Fabric:** Azure Portal → `sp500fabric` capacity → **Pause** first, then **Delete**.
2. **Databricks:** Azure Portal → `sp500-databricks` → **Delete**.
3. **Storage:** if Unity Catalog created a managed storage account, delete it too.
4. **Resource group:** Azure Portal → `rg-sp500` → **Delete resource group**. This
   removes everything in one shot — the safest final step. Type the group name to confirm.
5. **Verify:** Azure Portal → **Cost Management** → confirm daily spend drops to €0.
6. **Revoke the Databricks token** if you didn't delete the workspace earlier.

> After teardown, the repo still tells the full story: the dbt models run on DuckDB
> locally and in CI, and the screenshots prove the cloud deployment worked. That's the
> ideal portfolio state — reproducible for free, with evidence of cloud-scale execution.

---

## Quick reference: the four Databricks env vars

| `.env` variable | Where to find it in Databricks |
|-----------------|-------------------------------|
| `DATABRICKS_HOST` | SQL Warehouse → Connection details → Server hostname |
| `DATABRICKS_HTTP_PATH` | SQL Warehouse → Connection details → HTTP path |
| `DATABRICKS_TOKEN` | Settings → Developer → Access tokens → Generate |
| `DATABRICKS_CATALOG` | The catalog you created (`sp500`) |
