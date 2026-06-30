"""Ingest candidate AI industry-event news from the GDELT DOC 2.0 API.

This is the grounded replacement for the old hand-curated ``ai_industry_events`` seed.
GDELT indexes worldwide news; we pull articles about major AI announcements (model
launches, partnerships, large investments, regulation) across the lookback window.
Each row is a *candidate* article with a real source URL and publish date — the
``extraction/ai_event_extractor`` layer then uses an LLM to classify and de-duplicate
these candidates into structured industry events.

Pipeline position: public source (GDELT) -> Bronze ``ai_industry_news`` ->
LLM structuring (``ai_event_extractor``) -> Bronze ``ai_events`` -> dbt.

GDELT DOC API: https://api.gdeltproject.org/api/v2/doc/doc (free, no key).

Run: ``python -m ingestion.ai_industry_news [--months-back 60] [--max-per-month 200]``
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from ingestion.config import LOOKBACK_YEARS, bronze_path

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Focused query: major AI developments from the labs/vendors that move markets.
# GDELT query syntax: quoted phrases, OR groups, parentheses. Kept in English and
# scoped to AI so the LLM stage has relevant candidates to structure.
DEFAULT_QUERY = (
    '(("artificial intelligence" OR "generative AI" OR "large language model" '
    'OR ChatGPT OR Copilot OR Gemini OR "OpenAI" OR "Anthropic" OR "Nvidia AI") '
    'AND (launch OR partnership OR investment OR "billion" OR acquires OR '
    'acquisition OR regulation OR breakthrough OR unveils OR announces)) '
    'sourcelang:english'
)

# Reputable business/tech domains keep the candidate set signal-rich. GDELT can't
# hard-filter to a domain list in one call, so we keep this for optional post-filtering.
PREFERRED_DOMAINS = {
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com",
    "nytimes.com", "apnews.com", "venturebeat.com", "theinformation.com",
}

REQUEST_DELAY_SECONDS = 5.0  # GDELT asks for gentle polling


def _month_windows(months_back: int) -> list[tuple[datetime, datetime]]:
    """Return (start, end) datetimes for each month in the lookback window."""
    end = datetime.combine(date.today(), datetime.min.time())
    windows: list[tuple[datetime, datetime]] = []
    cursor = end
    for _ in range(months_back):
        start = cursor - timedelta(days=30)
        windows.append((start, cursor))
        cursor = start
    return windows


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def fetch_window(query: str, start: datetime, end: datetime, max_records: int) -> list[dict]:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(min(max_records, 250)),
        "sort": "HybridRel",
        "startdatetime": _fmt(start),
        "enddatetime": _fmt(end),
    }
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(GDELT_URL, params=params, timeout=60)
    resp.raise_for_status()
    # GDELT occasionally returns empty body / non-JSON when a window has no hits.
    try:
        payload = resp.json()
    except ValueError:
        return []
    return payload.get("articles", []) or []


def _parse_seendate(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest AI industry news from GDELT.")
    parser.add_argument(
        "--months-back", type=int, default=LOOKBACK_YEARS * 12,
        help="How many months of history to pull (default = lookback years * 12).",
    )
    parser.add_argument("--max-per-month", type=int, default=150, help="Max articles per month.")
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY, help="GDELT query string.")
    parser.add_argument(
        "--preferred-only", action="store_true",
        help="Keep only articles from the reputable-domain allow-list.",
    )
    args = parser.parse_args()

    records: list[dict] = []
    windows = _month_windows(args.months_back)
    print(f"Querying GDELT across {len(windows)} monthly windows...")
    for i, (start, end) in enumerate(windows, 1):
        try:
            articles = fetch_window(args.query, start, end, args.max_per_month)
        except requests.RequestException as exc:
            print(f"  window {i}/{len(windows)} {start:%Y-%m} failed: {exc}")
            continue
        for a in articles:
            domain = (a.get("domain") or "").lower()
            if args.preferred_only and domain not in PREFERRED_DOMAINS:
                continue
            records.append(
                {
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "domain": domain,
                    "seen_date": _parse_seendate(a.get("seendate")),
                    "language": a.get("language"),
                    "source_country": a.get("sourcecountry"),
                }
            )
        print(f"  window {i}/{len(windows)} {start:%Y-%m}: {len(articles)} articles")

    columns = ["title", "url", "domain", "seen_date", "language", "source_country"]
    df = pd.DataFrame(records, columns=columns)
    if not df.empty:
        df = df.dropna(subset=["url"]).drop_duplicates(subset=["url"]).reset_index(drop=True)
    out = bronze_path("ai_industry_news") / "ai_industry_news.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} candidate AI-news articles -> {out}")


if __name__ == "__main__":
    main()
