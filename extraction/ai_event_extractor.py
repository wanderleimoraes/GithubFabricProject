"""Structure candidate AI news (from GDELT) into industry events using Claude.

This is the grounded replacement for the hand-curated ``ai_industry_events`` seed.
It reads the Bronze ``ai_industry_news`` candidates (real article URLs + dates) and
asks Claude to identify the genuinely *notable* AI industry events, de-duplicate the
inevitable repeated coverage, and emit one structured row per event in the
``mart_ai_events`` shape — always keeping a real ``url`` and date from the source
articles so every event is traceable.

Pipeline position: Bronze ``ai_industry_news`` -> (this) -> Bronze ``ai_events`` -> dbt.

Run: ``python -m extraction.ai_event_extractor [--batch-size 40] [--max-batches N]``
"""

from __future__ import annotations

import argparse
import json
import os
import re

import pandas as pd
from anthropic import Anthropic

from ingestion.config import bronze_path

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Maps the AI labs/vendors that show up most to a related S&P 500 ticker when one
# clearly owns the story. Left null when no single public company is the subject.
VENDOR_TICKER = {
    "openai": "MSFT", "microsoft": "MSFT", "copilot": "MSFT",
    "google": "GOOGL", "deepmind": "GOOGL", "gemini": "GOOGL", "alphabet": "GOOGL",
    "nvidia": "NVDA", "meta": "META", "llama": "META",
    "amazon": "AMZN", "aws": "AMZN", "apple": "AAPL", "tesla": "TSLA",
}

EXTRACTION_PROMPT = """You are a technology-industry analyst. Below is a JSON list of \
news articles (title, date, domain, url) about artificial intelligence.

Identify the genuinely NOTABLE AI industry events they describe — major model or \
product launches, large investments/funding, significant partnerships, acquisitions, \
research breakthroughs, or regulation. De-duplicate: when several articles cover the \
same event, emit it ONCE, choosing the most authoritative article's url and the \
earliest date.

Return a JSON array. Each element must have exactly these keys:
- "event_date": the event date as "YYYY-MM-DD" (use the article date)
- "vendor": the primary organization (e.g. "OpenAI", "Nvidia", "Google", "EU")
- "event_name": a concise (<=12 word) neutral title of the event
- "category": one of "product_launch", "investment", "partnership", "acquisition", \
"research", "regulation", "other"
- "significance": one of "high", "medium", "low"
- "url": the source url, copied EXACTLY from one of the provided articles

Rules: only use the articles provided; never invent a url or an event not supported \
by them. Skip routine/opinion/duplicate coverage. If none qualify, return [].

Articles:
---
{articles}
---
Return only the JSON array, no prose."""


def _load_candidates() -> pd.DataFrame:
    path = bronze_path("ai_industry_news") / "ai_industry_news.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "ai_industry_news.parquet not found. Run "
            "`python -m ingestion.ai_industry_news` first."
        )
    df = pd.read_parquet(path)
    return df.dropna(subset=["url", "title"]).reset_index(drop=True)


def extract_events(client: Anthropic, batch: pd.DataFrame) -> list[dict]:
    articles = [
        {
            "title": r["title"],
            "date": str(r["seen_date"]) if pd.notna(r["seen_date"]) else None,
            "domain": r["domain"],
            "url": r["url"],
        }
        for _, r in batch.iterrows()
    ]
    message = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(articles=json.dumps(articles, default=str)),
        }],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _related_ticker(vendor: str | None) -> str | None:
    if not vendor:
        return None
    return VENDOR_TICKER.get(vendor.strip().lower())


def main() -> None:
    parser = argparse.ArgumentParser(description="Structure AI news into industry events.")
    parser.add_argument("--batch-size", type=int, default=40, help="Articles per LLM call.")
    parser.add_argument("--max-batches", type=int, default=None, help="Cap number of batches.")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. See .env.example.")

    client = Anthropic()
    candidates = _load_candidates()
    n_batches = (len(candidates) + args.batch_size - 1) // args.batch_size
    if args.max_batches:
        n_batches = min(n_batches, args.max_batches)
    print(f"Structuring {len(candidates)} candidate articles in {n_batches} batches...")

    records: list[dict] = []
    for b in range(n_batches):
        batch = candidates.iloc[b * args.batch_size:(b + 1) * args.batch_size]
        try:
            events = extract_events(client, batch)
        except Exception as exc:  # noqa: BLE001 - API/credit/auth error: stop, still write
            print(f"  extraction stopped ({exc}); writing {len(records)} events so far")
            break
        for e in events:
            records.append(
                {
                    "event_date": e.get("event_date"),
                    "vendor": e.get("vendor"),
                    "event_name": e.get("event_name"),
                    "category": e.get("category"),
                    "related_ticker": _related_ticker(e.get("vendor")),
                    "significance": e.get("significance"),
                    "url": e.get("url"),
                }
            )
        print(f"  batch {b + 1}/{n_batches}: +{len(events)} events")

    columns = ["event_date", "vendor", "event_name", "category", "related_ticker",
               "significance", "url"]
    df = pd.DataFrame(records, columns=columns)
    if not df.empty:
        df = df.dropna(subset=["event_name", "url"]).drop_duplicates(
            subset=["event_name", "event_date"]
        ).reset_index(drop=True)
    out = bronze_path("ai_events") / "ai_events.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} structured AI-event records -> {out}")


if __name__ == "__main__":
    main()
