"""Extract structured AI-investment commitments from SEC 8-K filings using Claude.

Pipeline:
  1. Read filing metadata from the Bronze ``filings`` dataset.
  2. Download each filing's primary document (HTML) from SEC.
  3. Ask Claude to extract any AI-related investment/commitment statements as JSON.
  4. Write the structured records to Bronze ``ai_commitments`` for dbt to model.

This converts unstructured disclosures into a queryable table — the NLP+ETL hybrid
that ``mart_ai_commitments`` depends on.

Run: ``python -m extraction.ai_commitment_extractor [--limit N]``
"""

from __future__ import annotations

import argparse
import os
import re
import time

import pandas as pd
import requests
from anthropic import Anthropic

from extraction.checkpoint import load_existing, load_processed, save_processed
from extraction.parsing import parse_json_array
from ingestion.config import bronze_path, sec_headers, SEC_REQUEST_DELAY_SECONDS

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

EXTRACTION_PROMPT = """You are a financial analyst extracting AI-investment commitments \
from an SEC filing.

Return a JSON array (possibly empty). Each element must have exactly these keys:
- "commitment_text": the verbatim sentence(s) describing the AI investment/commitment
- "amount_usd": the committed dollar amount as a number, or null if not quantified
- "category": one of "ai_infrastructure_capex", "ai_acquisition", "ai_partnership", \
"ai_product_investment", "other_ai"
- "confidence": your confidence in [0, 1] that this is a genuine AI investment commitment

Only include statements that are specifically about investing in or committing resources to \
artificial intelligence (compute, data centers for AI, AI startups, AI R&D programs, etc.).
If the filing contains no such statements, return [].

Filing text:
---
{filing_text}
---
Return only the JSON array, no prose."""


def _load_filings(limit: int | None, forms: set[str]) -> pd.DataFrame:
    path = bronze_path("filings") / "filings.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "filings.parquet not found. Run `python -m ingestion.edgar_filings` first."
        )
    df = pd.read_parquet(path)
    df = df[df["form"].isin(forms)]
    df = df.sort_values("filing_date", ascending=False)
    return df.head(limit) if limit else df


def fetch_document_text(url: str) -> str:
    """Download a filing document and strip it to plain text."""
    time.sleep(SEC_REQUEST_DELAY_SECONDS)
    resp = requests.get(url, headers=sec_headers(), timeout=30)
    resp.raise_for_status()
    text = re.sub(r"<[^>]+>", " ", resp.text)   # crude HTML strip
    text = re.sub(r"\s+", " ", text)
    return text[:60_000]                          # cap tokens / cost


def extract_commitments(client: Anthropic, filing_text: str) -> list[dict]:
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(filing_text=filing_text)}],
    )
    return parse_json_array(message.content[0].text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract AI commitments from SEC filings.")
    parser.add_argument("--limit", type=int, default=200, help="Max filings to process.")
    parser.add_argument(
        "--forms", nargs="+", default=["8-K", "10-K", "10-Q"],
        help="Filing forms to scan (10-K/10-Q carry richer AI discussion than 8-K).",
    )
    parser.add_argument(
        "--full-refresh", action="store_true",
        help="Ignore the checkpoint and re-extract everything from scratch.",
    )
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. See .env.example.")

    client = Anthropic()
    processed = set() if args.full_refresh else load_processed("ai_commitments")
    filings = _load_filings(args.limit, set(args.forms))
    filings = filings[~filings["accession_number"].isin(processed)]
    print(f"Scanning {len(filings)} {sorted(set(args.forms))} filings for AI commitments...")

    if processed:
        print(f"  checkpoint: skipping {len(processed)} already-processed filings")

    records: list[dict] = []
    done: set[str] = set()
    for _, f in filings.iterrows():
        if not f.get("document_url"):
            continue
        try:
            text = fetch_document_text(f["document_url"])
        except requests.RequestException as exc:
            print(f"  skip {f['ticker']} {f['accession_number']}: {exc}")
            continue
        try:
            items = extract_commitments(client, text)
        except Exception as exc:  # noqa: BLE001 - API/credit/auth error: stop, still write
            print(f"  extraction stopped ({exc}); writing {len(records)} records so far")
            break
        for item in items:
            records.append(
                {
                    "ticker": f["ticker"],
                    "event_date": f["filing_date"],
                    "commitment_text": item.get("commitment_text"),
                    "amount_usd": item.get("amount_usd"),
                    "category": item.get("category"),
                    "source_url": f["document_url"],
                    "confidence": item.get("confidence"),
                }
            )

        done.add(f["accession_number"])

    # Always write the full schema, even with zero records, so downstream dbt can
    # read the Parquet (an empty DataFrame would have no columns and fail to load).
    columns = [
        "ticker", "event_date", "commitment_text", "amount_usd", "category",
        "source_url", "confidence",
    ]
    df = pd.DataFrame(records, columns=columns)
    if not args.full_refresh:
        existing = load_existing("ai_commitments", "ai_commitments.parquet", columns)
        df = pd.concat([existing, df], ignore_index=True) if len(existing) else df
    out = bronze_path("ai_commitments") / "ai_commitments.parquet"
    df.to_parquet(out, index=False)
    save_processed("ai_commitments", (set() if args.full_refresh else processed) | done)
    print(f"Wrote {len(df)} AI-commitment records ({len(done)} filings newly processed) -> {out}")


if __name__ == "__main__":
    main()
