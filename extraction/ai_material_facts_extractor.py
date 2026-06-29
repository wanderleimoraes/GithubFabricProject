"""Extract material AI-related facts from SEC filings using Claude.

Broader sibling of ``ai_commitment_extractor``: that one captures *quantified
investment commitments*; this one captures **any material AI fact** a company
discloses — partnerships, product launches, capex/infrastructure, acquisitions,
research milestones, governance/risk statements, regulatory matters — at any level.

The design goal is **maximum interpretability**: every row carries the verbatim
quote, surrounding context, the filing item, the accession number, and a direct
``source_url`` to the filing document, so a reader can click through and judge the
fact for themselves rather than trusting a summary.

Pipeline:
  1. Read filing metadata from the Bronze ``filings`` dataset.
  2. Download each filing's primary document (HTML) from SEC and strip to text.
  3. Ask Claude to extract material AI facts as structured JSON.
  4. Write the records to Bronze ``ai_material_facts`` for dbt to model.

Run: ``python -m extraction.ai_material_facts_extractor [--limit N]``
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

import pandas as pd
import requests
from anthropic import Anthropic

from ingestion.config import bronze_path, sec_headers, SEC_REQUEST_DELAY_SECONDS

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

EXTRACTION_PROMPT = """You are an equity research analyst reading an SEC filing and \
extracting every MATERIAL fact related to artificial intelligence.

"Material AI fact" = any disclosure that a reasonable investor would consider \
significant about the company's AI strategy, position, or exposure — at any level. \
Include, but don't limit yourself to: AI partnerships or alliances, AI product or \
feature launches, AI infrastructure / data-center / compute capex, acquisitions of \
AI companies or talent, AI research milestones, AI-driven revenue or demand commentary, \
AI governance or ethics statements, and AI-related risks or regulatory matters.

Return a JSON array (possibly empty). Each element must have exactly these keys:
- "headline": a short (<=12 word) neutral summary of the fact
- "fact_text": the verbatim sentence(s) from the filing supporting it
- "context": one sentence on why it is material / how to interpret it
- "category": one of "partnership", "product", "infrastructure_capex", \
"acquisition", "research", "revenue_demand", "governance", "risk_regulatory", "other"
- "amount_usd": any dollar figure mentioned as a number, or null
- "significance": one of "high", "medium", "low"

Only include genuine AI-related facts. Do not invent or infer beyond the text. \
If the filing contains no material AI facts, return [].

Filing text:
---
{filing_text}
---
Return only the JSON array, no prose."""


def _load_filings(limit: int | None) -> pd.DataFrame:
    path = bronze_path("filings") / "filings.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "filings.parquet not found. Run `python -m ingestion.edgar_filings` first."
        )
    df = pd.read_parquet(path)
    df = df[df["form"] == "8-K"]
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


def extract_facts(client: Anthropic, filing_text: str) -> list[dict]:
    message = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(filing_text=filing_text)}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract material AI facts from 8-K filings.")
    parser.add_argument("--limit", type=int, default=25, help="Max filings to process.")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. See .env.example.")

    client = Anthropic()
    filings = _load_filings(args.limit)
    print(f"Scanning {len(filings)} 8-K filings for material AI facts...")

    records: list[dict] = []
    for _, f in filings.iterrows():
        if not f.get("document_url"):
            continue
        try:
            text = fetch_document_text(f["document_url"])
        except requests.RequestException as exc:
            print(f"  skip {f['ticker']} {f['accession_number']}: {exc}")
            continue
        try:
            items = extract_facts(client, text)
        except Exception as exc:  # noqa: BLE001 - API/credit/auth error: stop, still write
            print(f"  extraction stopped ({exc}); writing {len(records)} records so far")
            break
        for item in items:
            records.append(
                {
                    "ticker": f["ticker"],
                    "fact_date": f["filing_date"],
                    "headline": item.get("headline"),
                    "fact_text": item.get("fact_text"),
                    "context": item.get("context"),
                    "category": item.get("category"),
                    "amount_usd": item.get("amount_usd"),
                    "significance": item.get("significance"),
                    "form": f.get("form"),
                    "filing_item": f.get("items"),
                    "accession_number": f.get("accession_number"),
                    "source_url": f["document_url"],
                }
            )

    # Always write the full schema, even with zero records, so downstream dbt can
    # read the Parquet (an empty DataFrame would have no columns and fail to load).
    columns = [
        "ticker", "fact_date", "headline", "fact_text", "context", "category",
        "amount_usd", "significance", "form", "filing_item", "accession_number",
        "source_url",
    ]
    df = pd.DataFrame(records, columns=columns)
    out = bronze_path("ai_material_facts") / "ai_material_facts.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} material AI-fact records -> {out}")


if __name__ == "__main__":
    main()
