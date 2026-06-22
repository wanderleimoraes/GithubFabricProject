"""Ingest ~5 years of daily OHLCV prices for the S&P 500 from yfinance.

Run: ``python -m ingestion.market_prices [--limit N]``

``--limit`` restricts to the first N tickers (handy for local testing / CI).
"""

from __future__ import annotations

import argparse

import pandas as pd
import yfinance as yf

from ingestion.config import START_DATE, END_DATE, bronze_path
from ingestion.sp500_constituents import build as build_constituents


def _load_tickers(limit: int | None) -> list[str]:
    constituents_file = bronze_path("sp500_constituents") / "sp500_constituents.parquet"
    if constituents_file.exists():
        tickers = pd.read_parquet(constituents_file)["ticker"].tolist()
    else:
        tickers = build_constituents()["ticker"].tolist()
    return tickers[:limit] if limit else tickers


def fetch_prices(tickers: list[str]) -> pd.DataFrame:
    """Download daily prices and return a long, tidy DataFrame."""
    raw = yf.download(
        tickers=tickers,
        start=START_DATE.isoformat(),
        end=END_DATE.isoformat(),
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            continue
        sub = raw[ticker].reset_index()
        sub["ticker"] = ticker
        frames.append(sub)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.rename(
        columns={
            "Date": "trade_date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    df = df.dropna(subset=["close"])
    df["_ingested_at"] = pd.Timestamp.utcnow()
    cols = ["ticker", "trade_date", "open", "high", "low", "close", "adj_close", "volume", "_ingested_at"]
    return df[cols]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest daily OHLCV prices.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers.")
    args = parser.parse_args()

    tickers = _load_tickers(args.limit)
    print(f"Fetching prices for {len(tickers)} tickers ({START_DATE} -> {END_DATE})...")
    df = fetch_prices(tickers)
    out = bronze_path("market_prices") / "market_prices.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} price rows -> {out}")


if __name__ == "__main__":
    main()
