# Module 06 — Ingestion & public APIs  🌐 your machine

**Goal:** run the three ingestion scripts against real public APIs and replace the
synthetic Bronze data with real S&P 500 prices and XBRL fundamentals.

This is the first module that requires an internet connection. Everything runs on
your local machine in the same Python virtual environment.

---

## Concept

### What ingestion means in a data pipeline

"Ingestion" is the step that pulls data from external sources and writes it to the
Bronze layer — unchanged. The rule: **write what you received, not what you wish
you had.** No filtering, no type-casting, no joining. Bronze is the audit trail.
If a number in a report turns out wrong in six months, you replay from Bronze and
figure out when it went bad.

In this project, Bronze is Parquet files in `data/bronze/`. The ingestion scripts
are Python programs in `ingestion/` that call public APIs and write those files.

### The three sources

| Script | Source | What it fetches |
|--------|--------|-----------------|
| `sp500_constituents.py` | Wikipedia + SEC | 503 tickers, company names, GICS sectors, CIK numbers |
| `market_prices.py` | yfinance (Yahoo Finance) | 5 years of daily OHLCV prices per ticker |
| `edgar_fundamentals.py` | SEC EDGAR `companyfacts` API | All reported XBRL facts per company |

Run them in this order — `market_prices` and `edgar_fundamentals` both read the
output of `sp500_constituents` to get their ticker list.

### The CIK — SEC's internal company ID

The SEC doesn't identify companies by ticker (tickers change when companies rename
or merge). It uses a **Central Index Key (CIK)** — a stable numeric ID assigned
when a company first files with the SEC.

`sp500_constituents.py` does two things:
1. Fetches the S&P 500 list from Wikipedia (ticker, company name, sector).
2. Fetches `company_tickers.json` from the SEC to map every ticker to its CIK.

Every EDGAR API call uses CIK, not ticker. That's why the constituents script
runs first — every other script needs the CIK column.

### SEC's User-Agent requirement

The SEC allows free API access but requires a descriptive `User-Agent` header on
every request:

```
User-Agent: SP500 Portfolio Project you@example.com
```

Without it, you get HTTP 403 errors. The SEC also enforces a rate limit of ~10
requests per second. `config.py` adds a 0.12-second sleep between requests to
stay safely under that limit.

### yfinance

yfinance is a Python library that reverse-engineers Yahoo Finance's API. It
requires no API key, handles pagination, and returns data as a pandas DataFrame.
The `auto_adjust=False` flag tells it to return both raw close and adjusted close
(adjusted for dividends and stock splits) separately — we need both for the MA
and return calculations.

### The `--limit` flag

Both `market_prices.py` and `edgar_fundamentals.py` accept `--limit N`. This
restricts the run to the first N tickers, which is essential for:
- **Testing**: confirm the script works before you commit to 503 companies.
- **CI**: the GitHub Actions workflow runs with `--limit 3` so it finishes in
  seconds.

For a full S&P 500 run, expect `market_prices` to take ~2 minutes and
`edgar_fundamentals` ~10 minutes (503 API calls, 0.12s each, plus network).

---

## In this repo

- [`ingestion/config.py`](../ingestion/config.py) — shared paths, SEC headers,
  rate limit, time window. All scripts import from here.
- [`ingestion/sp500_constituents.py`](../ingestion/sp500_constituents.py) — step 1.
- [`ingestion/market_prices.py`](../ingestion/market_prices.py) — step 2.
- [`ingestion/edgar_fundamentals.py`](../ingestion/edgar_fundamentals.py) — step 3.
- [`.env.example`](../.env.example) — copy this to `.env` and fill in your values.

---

## Hands-on

All commands run from the repo root (`C:\dev\GithubFabricProject`) with the venv
active.

### 1. Set up `.env`

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code. The only required field for this module is:

```
SEC_USER_AGENT="SP500 Portfolio Project you@example.com"
DATA_DIR="C:/dev/GithubFabricProject/data"
```

The `SEC_USER_AGENT` string is read by `config.py` and sent with every EDGAR
request. Using your real email address is the SEC's requirement — they use it to
contact you if your script causes problems.

### 2. Fetch the constituents (always first)

```powershell
python -m ingestion.sp500_constituents
```

Expected output:
```
Wrote 503 constituents -> C:\dev\GithubFabricProject\data\bronze\sp500_constituents\sp500_constituents.parquet
```

This replaces the 3-company synthetic file with the real 503-company list. You can
verify:

```python
import duckdb
duckdb.sql("SELECT COUNT(*), COUNT(cik) FROM 'C:/dev/GithubFabricProject/data/bronze/sp500_constituents/sp500_constituents.parquet'").show()
```

You should see 503 rows and ~500 non-null CIKs (a handful of tickers may not have
a CIK match).

### 3. Fetch prices (test with --limit 5 first)

```powershell
python -m ingestion.market_prices --limit 5
```

This downloads 5 years of daily prices for the first 5 tickers only. Expected:

```
Fetching prices for 5 tickers (2021-06-xx -> 2026-06-xx)...
Wrote 6,278 price rows -> ...market_prices.parquet
```

Once you're happy it works, run the full fetch (takes ~2 minutes):

```powershell
python -m ingestion.market_prices
```

### 4. Fetch EDGAR fundamentals (test with --limit 3 first)

```powershell
python -m ingestion.edgar_fundamentals --limit 3
```

This fetches the `companyfacts` JSON for 3 companies from EDGAR. Expected output:
```
Fetching fundamentals for 3 companies...
Wrote 576 fundamental fact rows -> ...fundamentals.parquet
```

Once confirmed, run the full fetch (~10 minutes for all 503):

```powershell
python -m ingestion.edgar_fundamentals
```

*Note:* This is the only step with significant wait time. EDGAR limits you to
10 requests/second; with 503 companies that's ~60 seconds of mandatory sleep
plus network time. Let it run.

### 5. Rebuild dbt with real data

```powershell
cd dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
dbt seed --target duckdb
dbt build --target duckdb
```

With real data the models will now contain real company names, real prices, and
real financials. The tests (`PASS=8`) should still all pass — they're data-shape
assertions, not value assertions.

### 6. Query a real result

```python
import duckdb
con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")

# Real prices for a real company
con.sql("""
    SELECT company_name, trade_date,
           ROUND(close, 2)            AS close,
           ROUND(daily_return*100, 3) AS return_pct
    FROM main_gold.mart_prices
    WHERE ticker = 'MSFT'
    ORDER BY trade_date DESC
    LIMIT 5
""").show()
```

*What to notice:* real prices (MSFT closed around $400+ in 2024–2025), real return
percentages that fluctuate with market events, and today's date as the most recent
`trade_date`.

---

## Checkpoint

You're done with this module when:
- [ ] `sp500_constituents.parquet` has 503 rows.
- [ ] `market_prices.parquet` has prices for all 503 tickers (or at least 5 if you
      chose to skip the full run).
- [ ] `edgar_fundamentals.parquet` has rows from EDGAR (not the flat synthetic data).
- [ ] `dbt build` finishes with PASS (all tests green) on the real data.
- [ ] A query on `main_gold.mart_prices` returns realistic prices (not the
      synthetic $100 range).

---

## Exercises

1. **Inspect a real `companyfacts` response.** In a Python prompt:
   ```python
   import requests
   # MSFT CIK is 0000789019
   resp = requests.get(
       "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
       headers={"User-Agent": "SP500 Portfolio Project you@example.com"}
   )
   facts = resp.json()
   # List the us-gaap tags available for MSFT
   print(list(facts["facts"]["us-gaap"].keys())[:20])
   ```
   You'll see dozens of tags. Cross-reference with `WANTED_TAGS` in
   `edgar_fundamentals.py` — most are filtered out deliberately.

2. **Add a new tag.** Pick one tag from the list above that isn't in `WANTED_TAGS`
   and add it to both `WANTED_TAGS` in `edgar_fundamentals.py` and to
   `seeds/gaap_tag_mapping.csv`. Re-run `edgar_fundamentals` with `--limit 5`,
   then `dbt seed && dbt build`. Does the new metric appear in
   `main_silver.int_fundamentals_normalized`?

3. **Check freshness.** `_sources.yml` declares a freshness threshold for
   `market_prices`: warn after 48 hours, error after 7 days. Run:
   ```powershell
   dbt source freshness --target duckdb
   ```
   It should show the source as fresh (you just ingested it). If you re-run this
   command next week without re-ingesting, it will warn.

---

## Going deeper (optional)

- SEC EDGAR API docs (free, no auth required):
  <https://www.sec.gov/edgar/sec-api-documentation>
- yfinance docs: <https://ranaroussi.github.io/yfinance/>
- The XBRL taxonomy (why there are so many tag variants):
  <https://xbrl.fasb.org/us-gaap/>

---

**Next:** Module 07 — LLM extraction technique: using Claude to read SEC 8-K
filings and extract structured AI investment commitments from free-form text.
Say **"next"** when your checkpoint boxes are ticked.
