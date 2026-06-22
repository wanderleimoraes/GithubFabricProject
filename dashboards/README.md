# Dashboards (Power BI)

Power BI Desktop (free) connects natively to Databricks (or to the exported Gold
tables / DuckDB via ODBC for local development). This folder holds the `.pbix`
files and screenshots used in the project showcase.

> Commit the `.pbix` files and PNG screenshots here. Screenshots are what recruiters
> actually look at — keep them current in the root `README.md` too.

## Planned reports

### 1. Company-vs-company fundamentals
- **Source:** `mart_fundamentals`
- Two company slicers; line charts of revenue, net income, R&D, capex, margins over time.
- KPI cards for the latest period with YoY deltas.

### 2. AI investment commitments
- **Source:** `mart_ai_commitments` (+ `mart_fundamentals`)
- Ranked bar of committed AI $ by company.
- Slice/normalize by revenue, operating cash flow, total assets (use the
  `commitment_to_*_ratio` columns).
- Detail table with `commitment_text` and `source_url` for auditability.

### 3. Stock price + events overlay
- **Source:** `mart_prices`, `mart_fundamentals`, `mart_ai_events`
- Price line with `ma_50` / `ma_200`.
- **Tooltip A** on quarterly markers: EPS, revenue, net income for that period.
- **Tooltip B** on AI-event markers: company 8-K AI commitments + industry events
  (GPT-4, Claude, Gemini launches) to study price reaction.

### 4. NL Q&A
- Lives in the Streamlit app (`nl_query/`), embeddable as a tab/link.
- Optionally also use Power BI's built-in Copilot / Q&A visual on the same marts.

## Connecting Power BI to Databricks
`Get Data → Azure Databricks → Server hostname + HTTP path → Personal access token`,
then select the `sp500.gold` schema. Prefer **Import** mode for a portfolio (snappy,
works offline for demos); use DirectQuery if you want it always-live.
