"""Down-convert nanosecond timestamps in Bronze Parquet to microseconds.

Why: pandas writes Parquet timestamps as INT64 TIMESTAMP(NANOS), which Spark /
Databricks cannot read (it supports micro- and milli-second precision only).
This rewrites every Parquet file under data/bronze/ in place, casting any
nanosecond-timestamp column to microseconds. Lossless for daily/financial data.

Run: ``python -m scripts.convert_bronze_timestamps``
"""

from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

load_dotenv()

BRONZE_DIR = Path(os.getenv("DATA_DIR", "./data")) / "bronze"


def _downcast_schema(schema: pa.Schema) -> pa.Schema | None:
    """Return a new schema with ns timestamps changed to us, or None if no change."""
    changed = False
    fields = []
    for field in schema:
        t = field.type
        if pa.types.is_timestamp(t) and t.unit == "ns":
            fields.append(pa.field(field.name, pa.timestamp("us", tz=t.tz)))
            changed = True
        else:
            fields.append(field)
    return pa.schema(fields) if changed else None


def main() -> None:
    files = sorted(BRONZE_DIR.rglob("*.parquet"))
    if not files:
        raise SystemExit(f"No Parquet files found under {BRONZE_DIR.resolve()}")

    for path in files:
        table = pq.read_table(path)
        new_schema = _downcast_schema(table.schema)
        if new_schema is None:
            print(f"  ok (no ns timestamps): {path.name}")
            continue
        # safe=False allows truncating ns -> us
        table = table.cast(new_schema, safe=False)
        pq.write_table(table, path)
        print(f"  converted ns -> us: {path.name}")

    print(f"\nDone. Re-upload the files under {BRONZE_DIR.resolve()} to the volume.")


if __name__ == "__main__":
    main()
