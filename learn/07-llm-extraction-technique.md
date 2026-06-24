# Module 07 — LLM extraction technique  🌐 your machine

**Goal:** understand how the pipeline uses Claude to read unstructured SEC filings
and extract structured data from them — and run it against real 8-K filings.

This is the most technically interesting step in the project: turning free-form
legal text into a queryable table.

---

## Concept

### The problem: disclosures are prose, not data

When Microsoft announces "$50 billion in AI infrastructure investment", they don't
file a spreadsheet. They file an 8-K — a free-form HTML document that might say
something like:

> *"The Company intends to commit approximately fifty billion dollars over the
> next three years toward the expansion of its Azure AI computing infrastructure,
> including data centers and high-performance compute clusters."*

You cannot `SELECT amount FROM filings WHERE company = 'MSFT'` because `amount`
doesn't exist as a column. The information is buried in prose.

**LLM extraction** solves this by using a language model as a structured parser:
feed it the text, tell it exactly what schema to return, and it outputs JSON.

### The pipeline (four steps)

```
1. edgar_filings.py     → Bronze: filings.parquet
                           (8-K metadata: ticker, date, accession number, document URL)

2. ai_commitment_extractor.py → for each filing:
   a. Download the HTML document from SEC archives
   b. Strip HTML tags → plain text, capped at 60,000 characters
   c. Send to Claude with a structured extraction prompt
   d. Parse the JSON response → Bronze: ai_commitments.parquet

3. dbt build            → Silver: stg_ai_commitments
                        → Gold: mart_ai_commitments (joined to fundamentals)
```

### The prompt design

Read `EXTRACTION_PROMPT` in `extraction/ai_commitment_extractor.py`:

```python
EXTRACTION_PROMPT = """You are a financial analyst extracting AI-investment
commitments from an SEC filing.

Return a JSON array (possibly empty). Each element must have exactly these keys:
- "commitment_text": the verbatim sentence(s) describing the AI investment
- "amount_usd": the committed dollar amount as a number, or null if not quantified
- "category": one of "ai_infrastructure_capex", "ai_acquisition", "ai_partnership",
  "ai_product_investment", "other_ai"
- "confidence": your confidence in [0, 1] that this is a genuine AI investment

Only include statements specifically about investing in AI...
If the filing contains no such statements, return [].
...
Return only the JSON array, no prose."""
```

Four design choices worth understanding:

1. **Exact schema**: every key is named and typed. Claude knows `amount_usd` must
   be a number or null — not a string like "fifty billion".
2. **Closed enum for `category`**: five allowed values, no free text. This makes
   the column filterable without cleaning.
3. **`confidence` score**: a float in [0, 1]. You can filter out low-confidence
   extractions before analysis — auditability built in.
4. **"Return only the JSON array, no prose"**: without this, Claude might wrap
   the JSON in explanation text, breaking `json.loads()`.

### Cost and safety controls

- `text[:60_000]` — truncates filings to 60,000 characters before sending. An
  8-K is typically 5,000–30,000 characters; this cap prevents accidentally sending
  a massive exhibit and inflating the API bill.
- `--limit 25` is the default (25 filings per run). For 503 companies × ~20
  8-Ks each, a full run would cost real money. Start with `--limit 5`.
- The `try/except json.JSONDecodeError` returns `[]` on parse failure rather than
  crashing the whole pipeline. One bad LLM response doesn't lose the rest of the run.

---

## In this repo

- [`ingestion/edgar_filings.py`](../ingestion/edgar_filings.py) — step 1. Fetches
  8-K metadata from EDGAR `submissions` API. Must run before the extractor.
- [`extraction/ai_commitment_extractor.py`](../extraction/ai_commitment_extractor.py)
  — step 2. Downloads HTML, calls Claude, writes `ai_commitments.parquet`.
- [`models/staging/stg_ai_commitments.sql`](../dbt/sp500_analytics/models/staging/stg_ai_commitments.sql)
  — Silver staging: casts types, filters low-confidence extractions.
- [`models/marts/mart_ai_commitments.sql`](../dbt/sp500_analytics/models/marts/mart_ai_commitments.sql)
  — Gold mart: joins commitments to fundamentals so you can compare amount vs
  revenue / capex.

---

## Hands-on

From the repo root with venv active. Make sure your `.env` has:

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### 1. Fetch 8-K filing metadata (test with 5 companies)

```powershell
python -m ingestion.edgar_filings --limit 5
```

Expected output:
```
Fetching ['8-K'] filings for 5 companies...
Wrote 47 filing rows -> ...filings.parquet
```

The number varies — some companies file more 8-Ks than others. Each row has a
`document_url` pointing to the actual filing HTML on sec.gov.

### 2. Run the LLM extractor (test with 5 filings)

```powershell
python -m extraction.ai_commitment_extractor --limit 5
```

This sends up to 5 filings to Claude. Expected output:
```
Scanning 5 8-K filings for AI commitments...
Wrote N AI-commitment records -> ...ai_commitments.parquet
```

`N` could be 0 — most 8-Ks are routine press releases with no AI investment
language. That's expected and correct behaviour.

### 3. Inspect what Claude extracted

```python
import duckdb
duckdb.sql("""
    SELECT ticker, event_date, category,
           amount_usd / 1e9           AS amount_bn,
           ROUND(confidence, 2)       AS conf,
           LEFT(commitment_text, 120) AS excerpt
    FROM 'C:/dev/GithubFabricProject/data/bronze/ai_commitments/ai_commitments.parquet'
    ORDER BY event_date DESC
""").show()
```

*What to notice:*
- `amount_bn` is NULL for many rows — the company mentioned AI investment but
  didn't quantify it. That's honest: `null` is better than a hallucinated number.
- `confidence` < 0.7 rows are marginal extractions.
- `commitment_text` is the verbatim sentence from the filing — you can verify
  it by opening the `document_url` in a browser.

### 4. Run at a larger scale (optional, costs API credits)

```powershell
python -m ingestion.edgar_filings
python -m extraction.ai_commitment_extractor --limit 50
```

With 50 filings processed, you're likely to find quantified commitments —
especially for hyperscalers (MSFT, GOOGL, AMZN, META) which file frequent
AI-related 8-Ks.

### 5. Rebuild dbt

```powershell
cd dbt\sp500_analytics
$env:DATA_DIR = "C:\dev\GithubFabricProject\data"
$env:DBT_PROFILES_DIR = "C:\dev\GithubFabricProject\dbt\sp500_analytics\ci"
dbt build --target duckdb
```

Then query the Gold mart:

```python
import duckdb
con = duckdb.connect("C:/dev/GithubFabricProject/data/sp500.duckdb")

con.sql("""
    SELECT ticker, company_name, event_date, category,
           amount_usd / 1e9           AS amount_bn,
           ROUND(confidence, 2)       AS conf
    FROM main_gold.mart_ai_commitments
    WHERE confidence >= 0.7
    ORDER BY amount_usd DESC NULLS LAST
    LIMIT 10
""").show()
```

---

## Checkpoint

You're done with this module when:
- [ ] `edgar_filings` ran and wrote `filings.parquet` with at least one 8-K row.
- [ ] `ai_commitment_extractor` ran and wrote `ai_commitments.parquet` (even if
      it has 0 rows — that's correct if none of the 5 filings mentioned AI).
- [ ] You can explain the four keys in the extraction prompt and why each one exists.
- [ ] You can describe what `confidence` is for and how you'd use it as a filter.

---

## Exercises

1. **Verify an extraction.** Find a row in `ai_commitments.parquet` that has a
   non-null `commitment_text`. Copy the `document_url` and open it in a browser.
   Find the sentence Claude extracted. Is it accurate? Is the `amount_usd` right?
2. **Change the confidence threshold.** In
   `models/staging/stg_ai_commitments.sql`, find where confidence is filtered.
   Lower the threshold from 0.7 to 0.5 and run `dbt build`. Do more rows appear
   in `mart_ai_commitments`? Are they good extractions or noise?
3. **Add a new category.** Add `"ai_talent_acquisition"` to the `category` enum
   in `EXTRACTION_PROMPT`. Re-run the extractor on the same filings (`--limit 5`).
   Does Claude start tagging any different statements with the new category?

---

## Going deeper (optional)

- The extraction pattern (prompt → structured JSON) is sometimes called
  **"function calling"** or **"tool use"** in LLM APIs. Anthropic's version:
  <https://docs.anthropic.com/en/docs/tool-use>
- For higher-reliability extraction on long documents, look into Claude's
  extended context window and document-level prompting strategies.
- The `confidence` field is a simple form of **calibration** — asking the model
  to report its own uncertainty. For production systems you'd validate calibration
  empirically.

---

**Next:** Module 08 — Natural-language Q&A: building a text-to-SQL layer over
the marts so a user can ask questions in plain English. Say **"next"** when your
checkpoint boxes are ticked.
