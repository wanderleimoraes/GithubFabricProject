# Module 10 — Power BI Dashboards  🌐 your machine

**Goal:** build the four planned reports in Power BI Desktop, connect them to your
Gold mart data, and publish them to a Fabric workspace (when ready).

---

## Concept

### Power BI vocabulary

Four terms are used loosely but mean distinct things:

| Term | What it is |
|------|-----------|
| **Power BI Desktop** | Free Windows app — where you build everything. |
| **Power BI Service** | The cloud (app.powerbi.com) — where you publish and share. Fabric replaces this for Option C. |
| **Semantic model** | The data layer: connections to tables, relationships between them, and DAX measures. |
| **Report** | Visuals (charts, tables, cards) built on top of a semantic model. |

The workflow is always: **connect data → define semantic model → build report → publish.**
The semantic model is the brain; the report is the face.

### Import vs Direct Lake

| Mode | How it works | Best for |
|------|-------------|---------|
| **Import** | Power BI copies data into its in-memory engine at refresh time | Local dev, demos, datasets under ~1 GB |
| **DirectQuery** | Every visual fires a live query to the warehouse | Always-fresh data, larger datasets, slower visuals |
| **Direct Lake** | Power BI reads Parquet files from Fabric OneLake without copying | Fabric + Option C — the best of both |

For local DuckDB development you'll use **Import** (via CSV export). When you move to
Fabric you'll switch to **Direct Lake** — same report, same DAX, different connection.

### DAX — what it is and why you need it

**DAX** (Data Analysis Expressions) is Power BI's formula language. You use it to define
**measures** — calculations that don't exist as columns in your tables:

```
Net Margin % = DIVIDE(SUM(mart_fundamentals[net_income]),
                      SUM(mart_fundamentals[revenue]))
```

This is different from SQL: DAX measures re-evaluate dynamically based on whatever
filters (slicers, selections) the user applies. Click "Technology sector" and every
measure on the page recalculates for Technology only — automatically.

---

## In this repo

- [`dashboards/README.md`](../dashboards/README.md) — the four planned reports with
  source tables and visual descriptions.
- [`scripts/export_marts_csv.py`](../scripts/export_marts_csv.py) — exports the Gold
  mart tables from DuckDB to `data/export/*.csv` for local Power BI import.
- `dashboards/*.pbix` — the Power BI files you'll commit here after building them.
- `dashboards/*.png` — screenshots for the portfolio README.

---

## Hands-on

### Step 0 — Install Power BI Desktop

Download from the [Microsoft Store](https://aka.ms/pbidesktopstore) or
[direct download](https://powerbi.microsoft.com/desktop) — it's free. Windows only;
Mac users run it in a Windows VM or use Fabric's online report builder instead.

---

### Step 1 — Export Gold marts to CSV (local dev only)

Until you provision Databricks or Fabric, the easiest way to get data into Power BI is
to export the Gold mart tables to CSV. Run this from the repo root in **PowerShell**:

```powershell
python -m scripts.export_marts_csv
```

This writes four files to `data/export/`:
```
data/export/mart_fundamentals.csv
data/export/mart_prices.csv
data/export/mart_ai_commitments.csv
data/export/mart_ai_events.csv
```

---

### Step 2 — Load data into Power BI Desktop

1. Open Power BI Desktop → **Get Data → Text/CSV**.
2. Load all four CSV files. Each becomes a table in your semantic model.
3. In the **Model view** (left sidebar), set data types:
   - `trade_date`, `period_end`, `event_date` → **Date**
   - `revenue`, `net_income`, `close`, `amount_usd`, etc. → **Decimal Number**
   - `ticker`, `company_name`, `gics_sector` → **Text**

---

### Step 3 — Define relationships

In **Model view**, draw relationships between tables:

| From | To | On column |
|------|----|-----------|
| `mart_prices` | `mart_fundamentals` | `ticker` |
| `mart_ai_commitments` | `mart_fundamentals` | `ticker` |
| `mart_ai_events` | `mart_prices` | `event_date = trade_date` (approximate — use a date table for production) |

These relationships let visuals on one table filter another automatically.

---

### Step 4 — Add DAX measures

In the **Data view**, select `mart_fundamentals` and create these measures
(Home → New Measure):

```dax
Net Margin % =
    DIVIDE(SUM(mart_fundamentals[net_income]),
           SUM(mart_fundamentals[revenue]))

R&D Intensity =
    DIVIDE(SUM(mart_fundamentals[rnd_expense]),
           SUM(mart_fundamentals[revenue]))

YoY Revenue Growth =
VAR curr = CALCULATE(SUM(mart_fundamentals[revenue]),
                     mart_fundamentals[fiscal_year] = MAX(mart_fundamentals[fiscal_year]))
VAR prior = CALCULATE(SUM(mart_fundamentals[revenue]),
                      mart_fundamentals[fiscal_year] = MAX(mart_fundamentals[fiscal_year]) - 1)
RETURN DIVIDE(curr - prior, prior)
```

For `mart_ai_commitments`:
```dax
Total AI Committed ($B) =
    DIVIDE(SUM(mart_ai_commitments[amount_usd]), 1e9)

Avg Confidence =
    AVERAGE(mart_ai_commitments[confidence])
```

For `mart_prices`:
```dax
Latest Close =
    CALCULATE(MAX(mart_prices[close]),
              mart_prices[trade_date] = MAX(mart_prices[trade_date]))
```

---

### Step 5 — Build the four reports

Each report is a **page** inside one `.pbix` file (or separate files — your choice).

#### Report 1: Company vs Company Fundamentals

**Purpose:** compare any two companies across all financial metrics over time.

| Visual | Type | X | Y | Legend/Color |
|--------|------|---|---|---|
| Revenue over time | Line chart | `period_end` | `revenue` | `ticker` |
| Net margin over time | Line chart | `period_end` | `Net Margin %` | `ticker` |
| R&D intensity | Bar chart | `ticker` | `R&D Intensity` | `gics_sector` |
| Latest EPS | Card | — | `eps_diluted` | — |

Add a **Slicer** on `ticker` so users can pick which companies to compare.
Add a **Slicer** on `gics_sector` to filter by sector.

#### Report 2: AI Investment Commitments

**Purpose:** show which companies have publicly committed AI spend and how much.

| Visual | Type | X | Y | Notes |
|--------|------|---|---|-------|
| AI $ by company | Bar chart | `ticker` | `Total AI Committed ($B)` | Sort descending |
| Commitments over time | Line chart | `event_date` | `Total AI Committed ($B)` | Cumulative |
| Category breakdown | Pie chart | `category` | `Total AI Committed ($B)` | |
| Detail table | Table | `ticker`, `commitment_text`, `source_url`, `confidence` | | Provides auditability |

Add a **Slicer** on `category` and a **Slicer** on `confidence` (range slider: 0.7–1.0
to show only high-confidence records).

#### Report 3: Stock Price + Events Overlay

**Purpose:** show price history with moving averages and overlay AI events as markers.

| Visual | Type | Notes |
|--------|------|-------|
| Price + MAs | Line chart | `trade_date` on X; three lines: `close`, `ma_50`, `ma_200` |
| Volume | Column chart | `trade_date` on X, `volume` on Y — place below the price chart |
| AI events table | Table | `event_date`, `vendor`, `event_name`, `significance` — filter by the date range selected above |

Add a **Slicer** on `ticker` and a **Date range slicer** on `trade_date`.

The events overlay is the differentiating visual: you can visually inspect whether MSFT's
price moved after a Databricks or OpenAI announcement.

#### Report 4: NL Q&A

Power BI has a built-in **Q&A visual** — drag it onto a page and users can type questions
in plain English. Power BI maps column names to synonyms you define.

To configure it: select the Q&A visual → **Set up Q&A** → add synonyms for your columns
(e.g. `revenue` = "sales", "top line"; `net_margin` = "profit margin", "margin").

This is simpler than the Streamlit app but lives natively in the Power BI report with no
API key needed. The Streamlit app handles more complex multi-step SQL; the Q&A visual
handles simple lookups.

---

### Step 6 — What to commit

Save the `.pbix` file(s) to `dashboards/`. Then take screenshots of each report page
and save them as PNG:

```
dashboards/
├── sp500_analytics.pbix
├── report1_fundamentals.png
├── report2_ai_commitments.png
├── report3_price_events.png
└── report4_nlqa.png
```

Add the best screenshot to the root `README.md` — that's what recruiters see when they
land on the repo.

---

### Step 7 — Switching to Fabric Direct Lake (Option C)

When you've provisioned Databricks and Fabric:

1. Run `dbt build --target databricks` — Gold tables land in Databricks Unity Catalog
   (backed by ADLS Gen2 Delta files).
2. In Fabric: create a **Lakehouse** → **New shortcut** → Azure Data Lake Storage Gen2
   → point at the ADLS path where Databricks wrote the Delta tables.
3. In Fabric: **New semantic model** → select the shortcut tables → choose
   **Direct Lake** mode.
4. In Power BI Desktop: **Get Data → Power BI semantic models** → connect to the Fabric
   semantic model.
5. Your existing report pages (visuals, slicers, DAX measures) work unchanged —
   only the data source changed under the hood.

The `.pbix` file you built in Step 5 carries over directly. This is the value of
building on a semantic model: you swap the connection once, every report using that
model updates automatically.

---

## Checkpoint

- [ ] Power BI Desktop installed and open.
- [ ] All four CSV files loaded and data types set correctly.
- [ ] At least one DAX measure working (Net Margin % changing when you select a sector).
- [ ] Report 1 (Fundamentals) built with at least a revenue line chart and a ticker slicer.
- [ ] Report 3 (Price) built with `close`, `ma_50`, `ma_200` on the same axis.
- [ ] `.pbix` file committed to `dashboards/` with at least one screenshot.

---

## Exercises

1. **Format the measures.** Right-click `Net Margin %` → Format → Percentage, 1 decimal
   place. Right-click `Total AI Committed ($B)` → Format → Fixed decimal, 2 places.
   Clean formatting makes the report look professional.

2. **Add a tooltip page.** Create a new report page, set its page type to **Tooltip**.
   Add a table of `commitment_text` and `confidence`. Then set the AI commitments bar
   chart to use this page as its tooltip — hovering a bar shows the commitment details.

3. **Conditional formatting.** In Report 1, add conditional formatting to the net margin
   KPI card: green if positive, red if negative. (Select the card → Format →
   Conditional formatting.)

---

## Going deeper (optional)

- [Power BI Direct Lake overview](https://learn.microsoft.com/en-us/power-bi/enterprise/directlake-overview)
- [DAX guide](https://dax.guide) — reference for every DAX function with examples.
- [SQLBI — DAX patterns](https://www.daxpatterns.com) — the definitive DAX cookbook;
  the year-over-year growth pattern is covered in detail.
- [Fabric lakehouse tutorial](https://learn.microsoft.com/en-us/fabric/data-engineering/tutorial-lakehouse-introduction)

---

**Next:** Module 11 — Orchestration & CI. How to schedule the pipeline to run nightly
and what our GitHub Actions workflow does. Say **"next"** when your checkpoint boxes
are ticked.
