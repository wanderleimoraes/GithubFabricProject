# Architecture & Data Model

## 1. Design goals

- **End-to-end**: raw public data → lakehouse → modeled marts → AI-friendly analytics.
- **Cost-controlled**: free data sources; Azure Databricks running on the $200 new-account
  credit; everything else free or near-free (dbt Core, Power BI Desktop, DuckDB for local dev).
- **Recruiter-legible**: standard patterns (Medallion architecture, dbt layering, CI),
  clear documentation, and two genuinely differentiating features (LLM extraction + NL Q&A).

## 2. Platform: Azure Databricks + Medallion architecture

The lakehouse is organized into three Delta layers — the industry-standard
**Medallion** pattern that interviewers expect you to be able to explain:

| Layer | Catalog.schema | Contents | Written by |
|-------|----------------|----------|------------|
| **Bronze** | `sp500.bronze` | Raw ingested data, as-is from source, append-only with load metadata | `ingestion/` Python jobs |
| **Silver** | `sp500.silver` | Cleaned, typed, deduplicated, entity-resolved | dbt `staging` + `intermediate` |
| **Gold** | `sp500.gold` | Business-ready marts, conformed and tested | dbt `marts` |

**Local development mode:** the same dbt project runs against **DuckDB** (a single-file
warehouse) so the whole pipeline is testable offline and in CI without spending Databricks
credits. The warehouse is selected via the dbt `target` (`databricks` vs `duckdb`).

## 3. Source domains

| Domain | Source | Grain | Volume (5y, ~500 cos) |
|--------|--------|-------|------------------------|
| Market prices | yfinance | company × date (daily OHLCV) | ~0.6M rows |
| Fundamentals | SEC EDGAR XBRL `companyfacts` | company × fiscal period × metric | ~1–3M rows (long format) |
| Filings | SEC EDGAR `submissions` (8-K) | company × filing | ~50–100K rows |
| AI commitments / material facts | LLM extraction over 8-K / 10-K / 10-Q | company × event | derived, source-linked |
| AI industry events | Wikipedia AI timelines → LLM-structured | event date × vendor | derived, source-linked |

> **On "big data":** daily prices alone are small. Volume comes from breadth — the long-format
> EDGAR fundamentals (every XBRL fact, every period, every company) plus filings metadata push
> this into the multi-million-row range. If true big-data volume is a hard requirement later,
> the price grain can be dropped to intraday on a subset of tickers, but that trades off the
> "fully free, 5-year history" property (free APIs cap intraday history).

## 4. dbt layering

```
models/
├── staging/        # 1:1 with each Bronze source: rename, cast, light clean (= Silver entry)
│   ├── _sources.yml          # declares Bronze sources + freshness
│   ├── stg_market_prices.sql
│   ├── stg_fundamentals.sql
│   ├── stg_filings.sql
│   └── stg_ai_events.sql
├── intermediate/   # joins, dedup, entity resolution, derived metrics (= Silver)
│   ├── int_fundamentals_normalized.sql   # pivot/standardize XBRL tags → canonical metrics
│   └── int_prices_with_returns.sql        # daily/period returns, moving averages
└── marts/          # business-ready, tested, documented (= Gold)
    ├── _marts.yml                # tests + column docs (also the NL Q&A "schema brain")
    ├── mart_fundamentals.sql     # company × quarter × canonical metrics
    ├── mart_prices.sql           # company × date × price/return features
    ├── mart_ai_commitments.sql   # company × event_date × amount × source
    └── mart_ai_events.sql        # industry AI events for chart overlays
```

### Canonical fundamentals metrics

EDGAR XBRL is messy: the same concept is tagged differently across companies and over time.
`int_fundamentals_normalized` maps raw US-GAAP tags to a small canonical set:

| Canonical metric | Example US-GAAP tags |
|------------------|----------------------|
| `revenue` | `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax` |
| `net_income` | `NetIncomeLoss` |
| `operating_cash_flow` | `NetCashProvidedByUsedInOperatingActivities` |
| `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` |
| `rnd_expense` | `ResearchAndDevelopmentExpense` |
| `total_assets` | `Assets` |
| `cash_and_equivalents` | `CashAndCashEquivalentsAtCarryingValue` |

This normalization layer is the **core data-engineering showcase** — it is real, non-trivial
work that demonstrates handling messy source data.

## 5. AI-commitment extraction (LLM layer)

`extraction/ai_commitment_extractor.py` runs Claude over earnings-call transcripts and 8-K
exhibits to extract structured records:

```json
{
  "ticker": "MSFT",
  "event_date": "2024-01-30",
  "commitment_text": "...we expect capital expenditures to increase ... driven by AI infrastructure...",
  "amount_usd": 50000000000,
  "category": "ai_infrastructure_capex",
  "source_url": "https://www.sec.gov/...",
  "confidence": 0.82
}
```

Output lands in Bronze and is modeled by `mart_ai_commitments`. This converts unstructured
disclosures into a queryable table — the kind of NLP+ETL hybrid most DE portfolios lack.

## 6. Natural-language Q&A

`nl_query/app.py` (Streamlit) implements text-to-SQL:

1. Load the **dbt catalog** (`target/catalog.json` + `manifest.json`) → compact schema description.
2. Send the user's question + schema to Claude → SQL (read-only, validated against allowed tables).
3. Execute SQL on the warehouse (DuckDB locally / Databricks SQL in prod).
4. Ask Claude to produce a short narrative + a Plotly/Vega-Lite chart spec from the result.

Investing in dbt column descriptions pays off twice: documentation **and** the LLM's schema context.

## 7. Orchestration & CI

- **Orchestration**: Databricks Jobs (or a simple cron) — ingestion → `dbt build` → `dbt docs`.
- **CI** (`.github/workflows/ci.yml`): ruff lint + `dbt deps`/`dbt parse`/`dbt build` against
  DuckDB on every PR, so the modeling layer is verified without cloud spend.

## 8. Cost summary

| Item | Cost |
|------|------|
| Data sources | $0 |
| dbt Core, DuckDB, Power BI Desktop | $0 |
| Claude API (portfolio-scale usage) | a few $ |
| Azure Databricks | covered by $200 new-account credit; ~$50–80 if disciplined |
| GitHub (public repo) | $0 |
