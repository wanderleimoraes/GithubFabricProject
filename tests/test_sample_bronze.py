"""The CI sample-data generator must produce every Bronze dataset dbt sources expect."""

import os
import subprocess
import sys

EXPECTED_DATASETS = [
    "sp500_constituents",
    "market_prices",
    "fundamentals",
    "filings",
    "ai_commitments",
    "ai_material_facts",
    "ai_events",
]


def test_generator_writes_all_bronze_datasets(tmp_path):
    env = {**os.environ, "DATA_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "scripts.generate_sample_bronze"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    for dataset in EXPECTED_DATASETS:
        parquet = tmp_path / "bronze" / dataset / f"{dataset}.parquet"
        assert parquet.exists(), f"missing sample dataset: {dataset}"
        assert parquet.stat().st_size > 0
