"""Checkpointing for the SEC extraction jobs.

LLM extraction costs real money per filing, so re-runs must not re-extract filings
that were already processed. Each dataset keeps a sidecar Parquet of processed
accession numbers next to its output; a new run skips those, extracts only new
filings, and appends to the existing records. ``--full-refresh`` wipes the slate.
"""

from __future__ import annotations

import pandas as pd

from ingestion.config import bronze_path

CHECKPOINT_FILE = "processed_accessions.parquet"


def load_processed(dataset: str) -> set[str]:
    """Accession numbers already extracted for this dataset (empty set if none)."""
    path = bronze_path(dataset) / CHECKPOINT_FILE
    if not path.exists():
        return set()
    return set(pd.read_parquet(path)["accession_number"].dropna())


def save_processed(dataset: str, accessions: set[str]) -> None:
    path = bronze_path(dataset) / CHECKPOINT_FILE
    pd.DataFrame({"accession_number": sorted(accessions)}).to_parquet(path, index=False)


def load_existing(dataset: str, filename: str, columns: list[str]) -> pd.DataFrame:
    """Previously written records, or an empty frame with the right schema."""
    path = bronze_path(dataset) / filename
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_parquet(path)
