"""Ingest filing metadata (focused on 8-K material events) from SEC EDGAR.

8-K filings are how companies disclose material events — including many AI-related
announcements and capex commitments. This job pulls the recent filing index per
company; the filing documents themselves are fetched on demand by the LLM
extraction layer (``extraction/ai_commitment_extractor.py``).

Run: ``python -m ingestion.edgar_filings [--limit N] [--forms 8-K 10-K]``

API docs: https://www.sec.gov/edgar/sec-api-documentation
"""

from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

from ingestion.config import START_DATE, bronze_path, sec_headers, SEC_REQUEST_DELAY_SECONDS
from ingestion.sp500_constituents import build as build_constituents

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"


def _load_companies(limit: int | None) -> pd.DataFrame:
    constituents_file = bronze_path("sp500_constituents") / "sp500_constituents.parquet"
    df = (
        pd.read_parquet(constituents_file)
        if constituents_file.exists()
        else build_constituents()
    )
    df = df.dropna(subset=["cik"])
    return df.head(limit) if limit else df


def fetch_submissions(cik: str) -> dict | None:
    time.sleep(SEC_REQUEST_DELAY_SECONDS)
    resp = requests.get(SUBMISSIONS_URL.format(cik=cik), headers=sec_headers(), timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def extract_filings(ticker: str, cik: str, submissions: dict, forms: set[str]) -> list[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return []
    frame = pd.DataFrame(recent)
    if frame.empty:
        return []
    frame = frame[frame["form"].isin(forms)]
    frame = frame[frame["filingDate"] >= START_DATE.isoformat()]

    rows: list[dict] = []
    cik_int = int(cik)
    for _, f in frame.iterrows():
        accession_nodash = f["accessionNumber"].replace("-", "")
        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "form": f["form"],
                "filing_date": f["filingDate"],
                "report_date": f.get("reportDate"),
                "accession_number": f["accessionNumber"],
                "primary_document": f.get("primaryDocument"),
                "items": f.get("items"),
                "document_url": ARCHIVE_URL.format(
                    cik_int=cik_int,
                    accession_nodash=accession_nodash,
                    primary_doc=f.get("primaryDocument", ""),
                ),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR filing metadata.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies.")
    parser.add_argument("--forms", nargs="+", default=["8-K"], help="Filing forms to keep.")
    args = parser.parse_args()

    companies = _load_companies(args.limit)
    forms = set(args.forms)
    print(f"Fetching {sorted(forms)} filings for {len(companies)} companies...")

    all_rows: list[dict] = []
    for _, row in companies.iterrows():
        submissions = fetch_submissions(row["cik"])
        if submissions is None:
            continue
        all_rows.extend(extract_filings(row["ticker"], row["cik"], submissions, forms))

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["_ingested_at"] = pd.Timestamp.utcnow()
    out = bronze_path("filings") / "filings.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} filing rows -> {out}")


if __name__ == "__main__":
    main()
