"""Ingest candidate AI-event source text from Wikipedia's AI timeline pages.

The grounded replacement for the old hand-curated ``ai_industry_events`` seed.
Wikipedia maintains curated, citation-backed timelines of AI developments that span
years — unlike a news API, which only indexes recent months. We pull the plain text
of those pages, chunk it, and write Bronze ``ai_event_sources`` candidates. The
``extraction/ai_event_extractor`` layer then uses an LLM to turn the text into
structured industry events, each carrying the Wikipedia page as its ``url``.

Pipeline position: Wikipedia -> Bronze ``ai_event_sources`` ->
LLM structuring (``ai_event_extractor``) -> Bronze ``ai_events`` -> dbt.

MediaWiki API: https://en.wikipedia.org/w/api.php (free, no key; needs a UA).

Run: ``python -m ingestion.ai_events_wikipedia [--pages "Title" ...]``
"""

from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

from ingestion.config import bronze_path

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE_URL = "https://en.wikipedia.org/wiki/{title}"
USER_AGENT = "SP500-Portfolio/1.0 (AI timeline ingestion; contact via repo)"
REQUEST_DELAY_SECONDS = 1.0
CHUNK_CHARS = 4000

# Curated, citation-backed AI timeline pages covering the ~5-year window.
DEFAULT_PAGES = [
    "Timeline of artificial intelligence",
    "2026 in artificial intelligence",
    "2025 in artificial intelligence",
    "2024 in artificial intelligence",
    "2023 in artificial intelligence",
    "2022 in artificial intelligence",
]


def fetch_page_text(title: str) -> str | None:
    """Return the plain-text extract of a Wikipedia page, or None if it doesn't exist."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
    }
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(
        WIKI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=60
    )
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    for _, page in pages.items():
        if "missing" in page:
            return None
        return page.get("extract")
    return None


def _chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split on paragraph boundaries into <=size pieces to keep LLM calls bounded."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 > size and current:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest AI timeline text from Wikipedia.")
    parser.add_argument("--pages", nargs="+", default=DEFAULT_PAGES, help="Wikipedia page titles.")
    args = parser.parse_args()

    records: list[dict] = []
    print(f"Fetching {len(args.pages)} Wikipedia AI-timeline pages...")
    for title in args.pages:
        try:
            text = fetch_page_text(title)
        except requests.RequestException as exc:
            print(f"  skip '{title}': {exc}")
            continue
        if not text:
            print(f"  '{title}': not found")
            continue
        url = WIKI_PAGE_URL.format(title=title.replace(" ", "_"))
        page_chunks = _chunks(text)
        for chunk in page_chunks:
            records.append(
                {
                    "title": title,
                    "content": chunk,
                    "url": url,
                    "published_date": None,  # the event date is parsed from content
                    "domain": "en.wikipedia.org",
                }
            )
        print(f"  '{title}': {len(page_chunks)} chunks")

    columns = ["title", "content", "url", "published_date", "domain"]
    df = pd.DataFrame(records, columns=columns)
    out = bronze_path("ai_event_sources") / "ai_event_sources.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} candidate event-source chunks -> {out}")


if __name__ == "__main__":
    main()
