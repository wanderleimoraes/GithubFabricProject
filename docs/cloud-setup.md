# Cloud Architecture — Azure Databricks → Microsoft Fabric → Direct Lake (Option C)

This document covers the **fundamentals** of how the project runs in the cloud: the
architecture, the components, and the key engineering decisions. It is intentionally
conceptual — the step-by-step build log (portal clicks, grants, troubleshooting) is kept
out of the public repo and lives in the project's learning syllabus.

> The whole platform is **reproducible for free**: the dbt models build on DuckDB locally
> and in CI. The cloud deployment below is the same dbt project pointed at Databricks +
> Fabric, and is treated as temporary (provisioned on Azure credit, torn down after).

---

## The path, end to end

```
SEC EDGAR + yfinance  →  Azure Databricks (dbt medallion)  →  Microsoft Fabric
   (public data)            Bronze → Silver → Gold              OneLake mirror
                            Unity Catalog `sp500.gold`               │
                                                                     ▼
                                                       Direct Lake semantic model
                                                                     │
                                                                     ▼
                                                   Fabric Data Agent  +  Power BI
                                                   (natural-language Q&A)
```

1. **Azure Databricks** runs `dbt build --target databricks`, materialising the Gold
   star schema (`dim_tickers` hub + fact marts) into a Unity Catalog `sp500.gold` schema
   as Delta tables.
2. **Microsoft Fabric** mirrors that catalog into **OneLake** with a *Mirrored Azure
   Databricks catalog* — zero-copy, name-based, auto-synced.
3. A **Direct Lake** semantic model is built over the mirrored tables, rebuilding the
   star schema with DAX measures and business descriptions.
4. A **Fabric Data Agent** answers natural-language questions over that model (the
   project's "ask it yourself" endpoint); Power BI reports read the same model.

---

## Components

| Component | Role |
|-----------|------|
| **Azure Databricks** (Premium) | Compute + Unity Catalog; runs the dbt cloud build. |
| **Unity Catalog `sp500`** | Governed catalog; `silver` / `gold` schemas hold the dbt outputs. |
| **Databricks SQL Warehouse** | The endpoint dbt connects to (`DATABRICKS_HTTP_PATH`). |
| **Entra ID `fabricadmin@…`** | Org account Fabric accepts (personal Gmail is blocked). |
| **Fabric F2 capacity** | Smallest SKU; backs the workspace. Pause when idle. |
| **Mirrored Databricks catalog** | Zero-copy view of `sp500.gold` in OneLake. |
| **Direct Lake semantic model** | Star schema + DAX, read directly from OneLake Delta. |
| **Fabric Data Agent** | NL Q&A grounded on the model + ontology descriptions. |

---

## Key decisions (the "why")

- **Why Direct Lake (not Import/DirectQuery).** Direct Lake reads Delta straight from
  OneLake — Import speed with no refresh, DirectQuery freshness without the round-trips.
  It falls back to DirectQuery on unsupported features, which is *why transforms stay
  upstream in dbt* and the model stays thin.

- **Why mirror the catalog (not a raw ADLS shortcut).** The Gold marts are Unity Catalog
  *managed* tables, whose physical paths are opaque GUID folders. The Mirrored Azure
  Databricks catalog discovers tables **by name** and stays in sync — robust where a raw
  storage shortcut would be fragile.

- **Why F2 (not F64).** A single-user portfolio with a small Direct Lake model needs only
  2 CU. The Data Agent and ontology run on low SKUs; F64 is the enterprise/Copilot default.

- **Why cross-region (Fabric in Sweden Central, Databricks in West Europe).** West Europe
  Fabric quota was unavailable for a new subscription, so Fabric F2 was provisioned in a
  region that had quota. The mirror reads the Delta cross-region — negligible at this
  scale, and a clean illustration that **compute region is decoupled from storage region**
  over a OneLake mirror.

- **Why an ontology layer.** A hand-authored semantic layer (entities, relationships,
  metric glossary, time-window rules) grounds the NL engines so they answer multi-table,
  comparative, and temporal questions reliably instead of guessing joins. The same
  vocabulary backs both the Fabric Data Agent and the Streamlit text-to-SQL app — see
  [`docs/fabric-data-agent-instructions.md`](fabric-data-agent-instructions.md) and
  [`nl_query/ontology.py`](../nl_query/ontology.py).

---

## Conversational NL Q&A — engine vs. surface

An "ask it yourself" experience has two separable layers:

| Layer | What it is | Options |
|-------|-----------|---------|
| **Engine** | The brain that answers | Fabric Data Agent (Azure OpenAI GPT) grounded on the model/ontology, *or* a custom Claude text-to-SQL app |
| **Surface** | Where the user types | Copilot in Power BI (native), Claude via MCP, or the Streamlit chat box |

The engine and surface are independent — the same ontology-grounded engine can be reached
from multiple surfaces. The Fabric Data Agent runs on **Azure OpenAI GPT** (not Claude);
Claude reaches it as a **tool over MCP**. The native **Fabric IQ Ontology** (preview) can
be *generated from the Power BI semantic model* — the native implementation of
`nl_query/ontology.py`.

For Fabric-specific authoring, Microsoft maintains reusable AI skills at
[`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric) (clone it
and run Claude Code inside for auto-loaded Fabric expertise).

---

## Cost discipline

- **Auto-terminate** Databricks compute (10–20 min idle).
- **Pause** the Fabric capacity when not building (F2 bills per hour while active).
- The Azure resources are temporary — tear them down after the credit window. The durable
  portfolio artifacts are the repo, the screenshots, and the `.pbix`.

---

## The four Databricks connection variables

| `.env` variable | Source |
|-----------------|--------|
| `DATABRICKS_HOST` | SQL Warehouse → Connection details → Server hostname |
| `DATABRICKS_HTTP_PATH` | SQL Warehouse → Connection details → HTTP path (`/sql/1.0/warehouses/<id>`) |
| `DATABRICKS_TOKEN` | Settings → Developer → Access tokens |
| `DATABRICKS_CATALOG` | The Unity Catalog catalog (`sp500`) |

> The detailed, click-by-click deployment walkthrough (with the snags hit and how they
> were resolved) is maintained as a hands-on lesson in the project's learning syllabus,
> not in this public document.
