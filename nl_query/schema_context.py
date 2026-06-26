"""Build a compact schema description for the LLM from the dbt catalog.

Reading the dbt-generated ``catalog.json`` + ``manifest.json`` means the model sees
exactly the documented columns of the Gold marts — the dbt docs double as the LLM's
"schema brain". Falls back to a static description if the catalog isn't present.
"""

from __future__ import annotations

import json
from pathlib import Path

DBT_TARGET = Path(__file__).resolve().parents[1] / "dbt" / "sp500_analytics" / "target"

ALLOWED_PREFIXES = ("mart_", "dim_")

STATIC_FALLBACK = """
Tables (Gold marts + dimension):
- dim_tickers(ticker, company_name, gics_sector, gics_sub_industry, cik)
- mart_fundamentals(ticker, company_name, gics_sector, fiscal_year, fiscal_period,
    period_end, revenue, net_income, operating_income, rnd_expense, capex,
    operating_cash_flow, total_assets, stockholders_equity, eps_diluted,
    net_margin, rnd_intensity)
- mart_prices(ticker, company_name, gics_sector, trade_date, close, adj_close,
    volume, daily_return, ma_50, ma_200)
- mart_ai_commitments(ticker, company_name, event_date, commitment_text, amount_usd,
    category, source_url, confidence, latest_revenue, commitment_to_revenue_ratio)
- mart_ai_events(event_date, vendor, event_name, category, related_ticker,
    significance, url)
""".strip()


def build_schema_context() -> str:
    catalog_path = DBT_TARGET / "catalog.json"
    manifest_path = DBT_TARGET / "manifest.json"
    if not (catalog_path.exists() and manifest_path.exists()):
        return STATIC_FALLBACK

    catalog = json.loads(catalog_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    descriptions = {
        node["name"]: node.get("description", "")
        for node in manifest.get("nodes", {}).values()
    }

    lines: list[str] = ["Tables (Gold marts):"]
    for node in catalog.get("nodes", {}).values():
        name = node["metadata"]["name"]
        if not name.startswith(ALLOWED_PREFIXES):
            continue
        cols = ", ".join(node["columns"].keys())
        desc = descriptions.get(name, "")
        lines.append(f"- {name}: {desc}\n    columns: {cols}")
    return "\n".join(lines)


def allowed_tables() -> set[str]:
    """Tables the generated SQL is permitted to reference."""
    return {
        "dim_tickers",
        "mart_fundamentals",
        "mart_prices",
        "mart_ai_commitments",
        "mart_ai_events",
    }
