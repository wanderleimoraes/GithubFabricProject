"""Upload local Bronze Parquet files to Databricks and register them as Delta tables.

Replaces the manual routine (portal upload to a Unity Catalog volume + hand-run
CREATE TABLE in the SQL editor) with one command, so the whole refresh path —
ingest -> extract -> upload -> dbt build — is scriptable end to end.

For each dataset under ``data/bronze/``:
  1. upload ``<dataset>.parquet`` to ``/Volumes/<catalog>/bronze/raw/``
  2. run ``CREATE OR REPLACE TABLE <catalog>.bronze.<dataset> AS SELECT * FROM parquet.`...```

Auth: the standard four env vars (``DATABRICKS_HOST``, ``DATABRICKS_TOKEN``,
``DATABRICKS_HTTP_PATH`` for the SQL warehouse, ``DATABRICKS_CATALOG``).
Requires ``pip install databricks-sdk``.

Run: ``python -m scripts.upload_bronze_databricks [--datasets name ...]``
"""

from __future__ import annotations

import argparse
import io
import os

from ingestion.config import BRONZE_DIR

DEFAULT_DATASETS = [
    "sp500_constituents",
    "market_prices",
    "fundamentals",
    "filings",
    "ai_commitments",
    "ai_material_facts",
    "ai_events",
]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is not set. See .env.example / docs/cloud-setup.md.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Bronze Parquet to Databricks.")
    parser.add_argument(
        "--datasets", nargs="+", default=DEFAULT_DATASETS,
        help="Bronze datasets to upload (default: all).",
    )
    args = parser.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError as exc:  # keep the base requirements lean; this is cloud-only
        raise SystemExit("databricks-sdk is required: pip install databricks-sdk") from exc

    host = _require_env("DATABRICKS_HOST")
    token = _require_env("DATABRICKS_TOKEN")
    http_path = _require_env("DATABRICKS_HTTP_PATH")
    catalog = os.getenv("DATABRICKS_CATALOG", "sp500")
    warehouse_id = http_path.rstrip("/").rsplit("/", 1)[-1]

    w = WorkspaceClient(host=f"https://{host.removeprefix('https://')}", token=token)

    for dataset in args.datasets:
        local = BRONZE_DIR / dataset / f"{dataset}.parquet"
        if not local.exists():
            print(f"  skip {dataset}: {local} not found")
            continue

        volume_path = f"/Volumes/{catalog}/bronze/raw/{dataset}.parquet"
        print(f"  {dataset}: uploading {local.stat().st_size:,} bytes -> {volume_path}")
        with open(local, "rb") as fh:
            w.files.upload(volume_path, io.BytesIO(fh.read()), overwrite=True)

        sql = (
            f"CREATE OR REPLACE TABLE {catalog}.bronze.{dataset} AS "
            f"SELECT * FROM parquet.`{volume_path}`"
        )
        print(f"  {dataset}: registering Delta table {catalog}.bronze.{dataset}")
        resp = w.statement_execution.execute_statement(
            statement=sql, warehouse_id=warehouse_id, wait_timeout="50s"
        )
        state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
        if state != "SUCCEEDED":
            error = resp.status.error.message if resp.status and resp.status.error else state
            raise SystemExit(f"CREATE TABLE failed for {dataset}: {error}")

    print("Done. Run `dbt build --target databricks` to rebuild Silver/Gold.")


if __name__ == "__main__":
    main()
