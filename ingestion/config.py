"""Shared configuration and small helpers for the ingestion layer."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths -------------------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
BRONZE_DIR = DATA_DIR / "bronze"

# --- SEC EDGAR ---------------------------------------------------------------
# SEC requires a descriptive User-Agent with contact info, and rate-limits to
# ~10 requests/sec. See https://www.sec.gov/os/webmaster-faq#developers
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SP500 Portfolio Project wanderleimoraes@gmail.com")
SEC_REQUEST_DELAY_SECONDS = 0.12  # stay comfortably under 10 req/s

# --- Time window -------------------------------------------------------------
LOOKBACK_YEARS = 5
START_DATE = date.today() - timedelta(days=365 * LOOKBACK_YEARS)
END_DATE = date.today()


def bronze_path(dataset: str) -> Path:
    """Return (and create) the Bronze output directory for a dataset."""
    path = BRONZE_DIR / dataset
    path.mkdir(parents=True, exist_ok=True)
    return path


def sec_headers() -> dict[str, str]:
    return {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
