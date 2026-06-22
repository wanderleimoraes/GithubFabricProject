"""Fetch the current S&P 500 constituents and map each ticker to its SEC CIK.

The constituent list comes from Wikipedia (free, no auth). The CIK mapping comes
from SEC's public ``company_tickers.json``. Output is the reference table every
other ingestion job joins against.

Run: ``python -m ingestion.sp500_constituents``
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from ingestion.config import bronze_path, sec_headers, SEC_REQUEST_DELAY_SECONDS

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def fetch_constituents() -> pd.DataFrame:
    """Return the S&P 500 list with ticker, company, sector, sub-industry."""
    tables = pd.read_html(WIKI_URL)
    df = tables[0]
    df = df.rename(
        columns={
            "Symbol": "ticker",
            "Security": "company_name",
            "GICS Sector": "gics_sector",
            "GICS Sub-Industry": "gics_sub_industry",
            "Headquarters Location": "headquarters",
            "Date added": "date_added",
            "CIK": "cik",
        }
    )
    # Wikipedia uses BRK.B style; yfinance uses BRK-B.
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    keep = ["ticker", "company_name", "gics_sector", "gics_sub_industry", "headquarters"]
    df = df[[c for c in keep if c in df.columns]].copy()
    return df


def fetch_cik_map() -> pd.DataFrame:
    """Return a ticker -> zero-padded 10-digit CIK mapping from SEC."""
    time.sleep(SEC_REQUEST_DELAY_SECONDS)
    resp = requests.get(SEC_TICKERS_URL, headers=sec_headers(), timeout=30)
    resp.raise_for_status()
    records = resp.json().values()
    rows = [
        {"ticker": r["ticker"].replace(".", "-"), "cik": f"{int(r['cik_str']):010d}"}
        for r in records
    ]
    return pd.DataFrame(rows).drop_duplicates("ticker")


def build() -> pd.DataFrame:
    constituents = fetch_constituents()
    cik_map = fetch_cik_map()
    merged = constituents.merge(cik_map, on="ticker", how="left")
    missing = int(merged["cik"].isna().sum())
    if missing:
        print(f"WARNING: {missing} tickers could not be mapped to a CIK.")
    return merged


def main() -> None:
    df = build()
    out = bronze_path("sp500_constituents") / "sp500_constituents.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} constituents -> {out}")


if __name__ == "__main__":
    main()
