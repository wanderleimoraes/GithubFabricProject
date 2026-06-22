"""Ingestion package: pull raw public data into the Bronze layer.

Each module is runnable as a script, e.g. ``python -m ingestion.market_prices --limit 10``.
In development mode data is written as Parquet under ``$DATA_DIR/bronze``; in production the
same DataFrames are written to Delta tables in ``sp500.bronze`` on Databricks.
"""
