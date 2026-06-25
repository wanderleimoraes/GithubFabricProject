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
`mart_prices`, `mart_fundamentals`, `mart_ai_commitments`, `mart_ai_events`.
**Screenshot this** → save to `dashboards/cloud_unity_catalog.png`.

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
   - **Size:** **F2** (smallest).
   - **Fabric capacity administrator:** select `fabricadmin@...`.
3. **Review + create** → **Create**.

> F2 bills ~€0.30/hr while running. **Pause it** (Azure Portal → the capacity resource
> → **Pause**) whenever you're not actively building.

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
4. In the model editor, add the **relationships** and **DAX measures** from
   [`learn/10-power-bi-dashboards.md`](../learn/10-power-bi-dashboards.md) (Steps 3–4).

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
