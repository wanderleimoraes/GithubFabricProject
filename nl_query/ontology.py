"""Hand-authored semantic layer ("ontology") for the SP500 marts.

This is the project's own lightweight ontology: it names the **entities**, the
**relationships** between them, and a **metric glossary** of business definitions —
the meaning a flat column list can't convey. Feeding this to the LLM is what lets it
answer complex (multi-table, comparative, temporal) questions reliably instead of
guessing joins or inventing definitions.

It is deliberately human-readable: the same entities/relationships/metrics described
here are the blueprint for the native Microsoft Fabric IQ Ontology we generate from the
Power BI semantic model once Fabric capacity is available (see docs/cloud-setup.md
Part G). Build it by hand now, generate the Fabric version later — same vocabulary.
"""

from __future__ import annotations

ENTITIES = """
Entities (business objects):
- Company — a single S&P 500 constituent. Canonical key: ticker. Lives in dim_tickers;
  its attributes (company_name, gics_sector, gics_sub_industry) are also denormalized
  onto the fact marts for convenience.
- Fundamentals — one Company's reported financials for one fiscal period
  (mart_fundamentals, grain = ticker + period_end).
- PriceDay — one Company's market data for one trading day
  (mart_prices, grain = ticker + trade_date).
- AICommitment — an AI-investment commitment a Company disclosed in an 8-K filing,
  extracted by the LLM layer (mart_ai_commitments, grain = ticker + event_date).
- AIEvent — an industry-wide AI event for context/overlay, not company-specific
  (mart_ai_events). related_ticker may be null.
""".strip()

RELATIONSHIPS = """
Relationships (how to join):
- Company is the hub. Fundamentals, PriceDay and AICommitment each relate
  many-to-one to Company on `ticker`. Join any fact to dim_tickers on ticker.
- Because company attributes are denormalized onto the facts, grouping by
  gics_sector can be done directly on mart_prices / mart_fundamentals; for
  mart_ai_commitments (no sector column) join dim_tickers to get gics_sector.
- AIEvent is standalone (industry-wide); relate to a Company only via
  related_ticker when it is set.
- "Sector peers" of a Company = other Companies sharing its gics_sector.
""".strip()

METRIC_GLOSSARY = """
Metric glossary (definitions — use these exact formulas):
- net_margin = net_income / revenue (precomputed column on mart_fundamentals).
- rnd_intensity = rnd_expense / revenue (precomputed on mart_fundamentals).
- YoY revenue growth = revenue / LAG(revenue) OVER (PARTITION BY ticker
  ORDER BY fiscal_year) - 1. Use fiscal_year ordering.
- Total AI committed = SUM(amount_usd) over mart_ai_commitments (USD; may be null
  when a commitment was unquantified — those rows are excluded by SUM).
- commitment_to_revenue_ratio = amount_usd / latest_revenue (precomputed).
- daily_return = one-day fractional price change (precomputed on mart_prices).
- ma_50 / ma_200 = 50- and 200-day moving averages of close (precomputed).
- "Latest" for a company means the row with the max period_end (fundamentals) or
  max trade_date (prices) for that ticker.
- Outperform / underperform vs sector = a Company's daily_return above / below the
  AVG(daily_return) of its gics_sector for the same trade_date.
""".strip()

EXAMPLES = """
Worked examples (question -> SQL):

Q: Top 5 companies by R&D intensity in the latest fiscal year.
SQL:
SELECT ticker, company_name, rnd_intensity
FROM mart_fundamentals
WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM mart_fundamentals)
ORDER BY rnd_intensity DESC
LIMIT 5;

Q: Total AI committed by sector.
SQL:
SELECT t.gics_sector, SUM(c.amount_usd) AS total_committed
FROM mart_ai_commitments c
JOIN dim_tickers t ON c.ticker = t.ticker
GROUP BY t.gics_sector
ORDER BY total_committed DESC;

Q: Apple's year-over-year revenue growth.
SQL:
SELECT fiscal_year, revenue,
       revenue / LAG(revenue) OVER (PARTITION BY ticker ORDER BY fiscal_year) - 1
         AS yoy_revenue_growth
FROM mart_fundamentals
WHERE ticker = 'AAPL'
ORDER BY fiscal_year;

Q: On the latest trading day, which companies outperformed their sector average?
SQL:
WITH latest AS (
    SELECT ticker, company_name, gics_sector, daily_return
    FROM mart_prices
    WHERE trade_date = (SELECT MAX(trade_date) FROM mart_prices)
)
SELECT ticker, company_name, gics_sector, daily_return
FROM latest l
WHERE daily_return > (
    SELECT AVG(daily_return) FROM latest peers
    WHERE peers.gics_sector = l.gics_sector
)
ORDER BY gics_sector, daily_return DESC;

Q: Which companies committed the most to AI relative to their revenue?
SQL:
SELECT ticker, company_name, amount_usd, latest_revenue, commitment_to_revenue_ratio
FROM mart_ai_commitments
WHERE commitment_to_revenue_ratio IS NOT NULL
ORDER BY commitment_to_revenue_ratio DESC
LIMIT 10;

Q: For companies that announced an AI commitment, what is their latest net margin?
SQL:
WITH latest_fund AS (
    SELECT ticker, net_margin,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY period_end DESC) AS rn
    FROM mart_fundamentals
)
SELECT c.ticker, c.company_name, c.amount_usd, f.net_margin
FROM mart_ai_commitments c
JOIN latest_fund f ON c.ticker = f.ticker AND f.rn = 1
ORDER BY c.amount_usd DESC;

Q: Highest-confidence AI commitments over $1 billion.
SQL:
SELECT ticker, company_name, event_date, amount_usd, confidence, commitment_text
FROM mart_ai_commitments
WHERE amount_usd >= 1000000000 AND confidence >= 0.8
ORDER BY amount_usd DESC;

Q: Total AI committed per calendar year.
SQL:
SELECT EXTRACT(year FROM event_date) AS commit_year,
       SUM(amount_usd) AS total_committed
FROM mart_ai_commitments
GROUP BY commit_year
ORDER BY commit_year;

Q: Do companies with higher R&D intensity also make larger AI commitments?
SQL:
WITH latest_fund AS (
    SELECT ticker, rnd_intensity,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY period_end DESC) AS rn
    FROM mart_fundamentals
)
SELECT c.ticker, c.company_name, f.rnd_intensity,
       SUM(c.amount_usd) AS total_ai_committed
FROM mart_ai_commitments c
JOIN latest_fund f ON c.ticker = f.ticker AND f.rn = 1
GROUP BY c.ticker, c.company_name, f.rnd_intensity
ORDER BY total_ai_committed DESC;
""".strip()


def build_ontology_context() -> str:
    """The full semantic-layer grounding block for the LLM prompt."""
    return "\n\n".join([ENTITIES, RELATIONSHIPS, METRIC_GLOSSARY, EXAMPLES])
