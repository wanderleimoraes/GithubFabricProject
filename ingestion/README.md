# Ingestion layer (Bronze)

Python jobs that pull raw public data into the **Bronze** layer. In development
they write Parquet under `$DATA_DIR/bronze/`; in production the same DataFrames are
written to Delta tables in `sp500.bronze` on Databricks.

## Jobs

| Module | Output dataset | Source | Notes |
|--------|----------------|--------|-------|
| `sp500_constituents` | `sp500_constituents` | Wikipedia + SEC `company_tickers.json` | Reference table (ticker ↔ CIK). Run this **first**. |
| `market_prices` | `market_prices` | yfinance | ~5y daily OHLCV |
| `edgar_fundamentals` | `fundamentals` | SEC EDGAR `companyfacts` | Long-format XBRL facts |
| `edgar_filings` | `filings` | SEC EDGAR `submissions` | 8-K (and other) filing metadata |

## Quickstart (local, small sample)

```bash
python -m ingestion.sp500_constituents
python -m ingestion.market_prices     --limit 10
python -m ingestion.edgar_fundamentals --limit 10
python -m ingestion.edgar_filings      --limit 10 --forms 8-K
```

## SEC etiquette

EDGAR requires a descriptive `User-Agent` with contact info and rate-limits to
~10 requests/second. Set `SEC_USER_AGENT` in your `.env`. The jobs sleep between
requests (`SEC_REQUEST_DELAY_SECONDS`) to stay within the limit.

## Running on Databricks

Wrap each `fetch_*` function in a Databricks notebook/job and replace the
`to_parquet(...)` sink with a Delta write, e.g.:

```python
spark.createDataFrame(df).write.mode("append").saveAsTable("sp500.bronze.market_prices")
```

The fetch functions are deliberately pure (return DataFrames) so the sink is swappable
between local Parquet and Delta without touching the extraction logic.
