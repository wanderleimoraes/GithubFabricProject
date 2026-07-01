"""Ingest XBRL fundamentals from SEC EDGAR's ``companyfacts`` API.

For each company (CIK) this pulls every reported US-GAAP fact and flattens it to a
long table: one row per (cik, tag, unit, fiscal period, value). The dbt
``int_fundamentals_normalized`` model later maps the raw tags to canonical metrics.

Run: ``python -m ingestion.edgar_fundamentals [--limit N]``

API docs: https://www.sec.gov/edgar/sec-api-documentation
"""

from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

from ingestion.config import bronze_path, sec_headers, SEC_REQUEST_DELAY_SECONDS
from ingestion.sp500_constituents import build as build_constituents

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Only keep tags we care about to keep volume manageable. Set to None to keep all.
WANTED_TAGS = {
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetIncomeLoss",
    "ResearchAndDevelopmentExpense",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "NetCashProvidedByUsedInOperatingActivities",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "OperatingIncomeLoss",
    "EarningsPerShareDiluted",
    # Share counts (unit: "shares") — enable market cap = shares x close downstream.
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "CommonStockSharesOutstanding",
}


def _load_companies(limit: int | None) -> pd.DataFrame:
    constituents_file = bronze_path("sp500_constituents") / "sp500_constituents.parquet"
    if constituents_file.exists():
        df = pd.read_parquet(constituents_file)
    else:
        df = build_constituents()
    df = df.dropna(subset=["cik"])
    return df.head(limit) if limit else df


def fetch_company_facts(cik: str) -> dict | None:
    time.sleep(SEC_REQUEST_DELAY_SECONDS)
    resp = requests.get(COMPANYFACTS_URL.format(cik=cik), headers=sec_headers(), timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def flatten_facts(ticker: str, cik: str, facts: dict) -> list[dict]:
    """Flatten one company's ``us-gaap`` facts into long rows."""
    rows: list[dict] = []
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag, payload in us_gaap.items():
        if WANTED_TAGS is not None and tag not in WANTED_TAGS:
            continue
        for unit, observations in payload.get("units", {}).items():
            for obs in observations:
                rows.append(
                    {
                        "ticker": ticker,
                        "cik": cik,
                        "tag": tag,
                        "unit": unit,
                        "value": obs.get("val"),
                        "fiscal_year": obs.get("fy"),
                        "fiscal_period": obs.get("fp"),
                        "form": obs.get("form"),
                        "period_start": obs.get("start"),
                        "period_end": obs.get("end"),
                        "filed": obs.get("filed"),
                        "frame": obs.get("frame"),
                    }
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR XBRL fundamentals.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies.")
    args = parser.parse_args()

    companies = _load_companies(args.limit)
    print(f"Fetching fundamentals for {len(companies)} companies...")

    all_rows: list[dict] = []
    for _, row in companies.iterrows():
        facts = fetch_company_facts(row["cik"])
        if facts is None:
            print(f"  no companyfacts for {row['ticker']} (CIK {row['cik']})")
            continue
        all_rows.extend(flatten_facts(row["ticker"], row["cik"], facts))

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["_ingested_at"] = pd.Timestamp.utcnow()
    out = bronze_path("fundamentals") / "fundamentals.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} fundamental fact rows -> {out}")


if __name__ == "__main__":
    main()
