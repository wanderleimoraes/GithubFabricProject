"""Export the Gold marts from the local DuckDB warehouse to the bundled sample
Parquet the deployed Streamlit app ships with (nl_query/sample_data/).

The deployed app has no warehouse — it loads these files into in-memory DuckDB.
Re-run this after `dbt build --target duckdb` (especially after ingesting real
data) to refresh the public snapshot, then commit the updated Parquet.

Run: ``python -m scripts.export_nl_query_sample``
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/sp500.duckdb")
OUT = Path(__file__).resolve().parents[1] / "nl_query" / "sample_data"
TABLES = [
    "dim_tickers",
    "mart_fundamentals",
    "mart_prices",
    "mart_ai_commitments",
    "mart_ai_events",
    "mart_ai_material_facts",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    con.execute("SET search_path = 'main_gold'")
    for t in TABLES:
        dest = OUT / f"{t}.parquet"
        con.execute(f"COPY (SELECT * FROM {t}) TO '{dest.as_posix()}' (FORMAT PARQUET)")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"wrote {n:>6} rows -> {dest.relative_to(OUT.parents[1])}")


if __name__ == "__main__":
    main()
