"""Generate small, deterministic synthetic Bronze data for CI and offline demos.

CI should verify the transformation layer (dbt models + tests) reproducibly,
without depending on live external services (Wikipedia, SEC, yfinance) that can
rate-limit, change format, or block requests. This script writes the same Bronze
datasets the ingestion jobs produce, but with tiny synthetic content.

Run: ``python -m scripts.generate_sample_bronze``
"""

from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pandas as pd

BASE = os.path.join(os.getenv("DATA_DIR", "./data"), "bronze")
SEED = 42


def _write(name: str, df: pd.DataFrame) -> None:
    out_dir = os.path.join(BASE, name)
    os.makedirs(out_dir, exist_ok=True)
    df.to_parquet(os.path.join(out_dir, f"{name}.parquet"), index=False)
    print(f"wrote {len(df):>5} rows -> {name}")


def main() -> None:
    rng = np.random.default_rng(SEED)
    now = pd.Timestamp.now("UTC")
    companies = [
        ("MSFT", "Microsoft", "0000789019"),
        ("NVDA", "NVIDIA", "0001045810"),
        ("GOOGL", "Alphabet", "0001652044"),
    ]

    _write(
        "sp500_constituents",
        pd.DataFrame(
            [
                {
                    "ticker": t,
                    "company_name": name,
                    "gics_sector": "Information Technology",
                    "gics_sub_industry": "Software",
                    "headquarters": "USA",
                    "cik": cik,
                }
                for t, name, cik in companies
            ]
        ),
    )

    dates = pd.bdate_range("2021-01-04", periods=300)
    price_rows = []
    for t, _, _ in companies:
        path = 100 + np.cumsum(rng.standard_normal(len(dates)))
        for d, c in zip(dates, path):
            price_rows.append(
                {
                    "ticker": t,
                    "trade_date": d.date(),
                    "open": c,
                    "high": c + 1,
                    "low": c - 1,
                    "close": c,
                    "adj_close": c,
                    "volume": 1_000_000,
                    "_ingested_at": now,
                }
            )
    _write("market_prices", pd.DataFrame(price_rows))

    fundamentals = []
    for t, _, cik in companies:
        for fy in (2022, 2023):
            for tag, val in [
                ("Revenues", 2e11),
                ("NetIncomeLoss", 6e10),
                ("ResearchAndDevelopmentExpense", 2e10),
                ("PaymentsToAcquirePropertyPlantAndEquipment", 3e10),
                ("NetCashProvidedByUsedInOperatingActivities", 8e10),
                ("Assets", 4e11),
            ]:
                fundamentals.append(
                    {
                        "ticker": t,
                        "cik": cik,
                        "tag": tag,
                        "unit": "USD",
                        "value": val,
                        "fiscal_year": fy,
                        "fiscal_period": "FY",
                        "form": "10-K",
                        "period_start": dt.date(fy, 1, 1),
                        "period_end": dt.date(fy, 12, 31),
                        "filed": dt.date(fy + 1, 1, 30),
                        "frame": None,
                        "_ingested_at": now,
                    }
                )
    _write("fundamentals", pd.DataFrame(fundamentals))

    _write(
        "filings",
        pd.DataFrame(
            [
                {
                    "ticker": "MSFT",
                    "cik": "0000789019",
                    "form": "8-K",
                    "filing_date": dt.date(2023, 1, 23),
                    "report_date": dt.date(2023, 1, 23),
                    "accession_number": "0000000000-23-000001",
                    "primary_document": "d.htm",
                    "items": "7.01",
                    "document_url": "https://example.com/filing",
                    "_ingested_at": now,
                }
            ]
        ),
    )

    _write(
        "ai_commitments",
        pd.DataFrame(
            [
                {
                    "ticker": "MSFT",
                    "event_date": dt.date(2023, 1, 23),
                    "commitment_text": "Sample synthetic AI investment commitment.",
                    "amount_usd": 1e10,
                    "category": "ai_partnership",
                    "source_url": "https://example.com/filing",
                    "confidence": 0.9,
                }
            ]
        ),
    )

    _write(
        "ai_material_facts",
        pd.DataFrame(
            [
                {
                    "ticker": "MSFT",
                    "fact_date": dt.date(2023, 1, 23),
                    "headline": "Microsoft extends OpenAI partnership",
                    "fact_text": "Synthetic verbatim text describing a multiyear AI partnership.",
                    "context": "Signals deepening AI platform strategy.",
                    "category": "partnership",
                    "amount_usd": 1e10,
                    "significance": "high",
                    "form": "8-K",
                    "filing_item": "7.01",
                    "accession_number": "0000000000-23-000001",
                    "source_url": "https://example.com/filing",
                },
                {
                    "ticker": "NVDA",
                    "fact_date": dt.date(2024, 2, 21),
                    "headline": "Data-center AI demand drives revenue",
                    "fact_text": "Synthetic verbatim text on record data-center AI revenue.",
                    "context": "Quantifies AI-driven demand for the reader.",
                    "category": "revenue_demand",
                    "amount_usd": None,
                    "significance": "high",
                    "form": "8-K",
                    "filing_item": "2.02",
                    "accession_number": "0000000000-24-000002",
                    "source_url": "https://example.com/filing2",
                },
            ]
        ),
    )

    _write(
        "ai_events",
        pd.DataFrame(
            [
                {
                    "event_date": dt.date(2022, 11, 30),
                    "vendor": "OpenAI",
                    "event_name": "ChatGPT public launch",
                    "category": "product_launch",
                    "related_ticker": "MSFT",
                    "significance": "high",
                    "url": "https://example.com/news/chatgpt-launch",
                },
                {
                    "event_date": dt.date(2023, 1, 23),
                    "vendor": "Microsoft",
                    "event_name": "Microsoft extends multibillion-dollar OpenAI investment",
                    "category": "investment",
                    "related_ticker": "MSFT",
                    "significance": "high",
                    "url": "https://example.com/news/msft-openai",
                },
            ]
        ),
    )


if __name__ == "__main__":
    main()
