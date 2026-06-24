"""Export Gold mart tables from DuckDB to CSV for local Power BI import.

Writes one CSV per mart table to data/export/. Run this whenever the Gold
layer is rebuilt and you want to refresh the local Power BI data source.

Run: ``python -m scripts.export_marts_csv``
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/sp500.duckdb")
EXPORT_DIR = Path("./data/export")

MARTS = [
    "mart_fundamentals",
    "mart_prices",
    "mart_ai_commitments",
    "mart_ai_events",
]


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    con.execute("SET search_path = 'main_gold'")

    for mart in MARTS:
        out = EXPORT_DIR / f"{mart}.csv"
        con.execute(f"COPY (SELECT * FROM {mart}) TO '{out}' (HEADER, DELIMITER ',')")
        count = con.execute(f"SELECT COUNT(*) FROM {mart}").fetchone()[0]
        print(f"  {mart}: {count:,} rows → {out}")

    con.close()
    print(f"\nExported {len(MARTS)} tables to {EXPORT_DIR.resolve()}")


if __name__ == "__main__":
    main()
