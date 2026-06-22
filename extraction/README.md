# Extraction layer (LLM)

Turns unstructured disclosures into structured rows using Claude.

## `ai_commitment_extractor.py`

Reads 8-K filing metadata from Bronze, downloads each filing, and asks Claude to
extract AI-investment commitments as structured JSON. Output is written to
`bronze/ai_commitments/` and modeled by `mart_ai_commitments`.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m extraction.ai_commitment_extractor --limit 25
```

### Cost control
- Filing text is capped at ~60k characters per document.
- Start with `--limit` small; scale up once the prompt is tuned.
- Consider caching results by `accession_number` to avoid re-extracting.

### Quality notes
- Each record carries a `confidence` score; filter on it in the mart or dashboard.
- The prompt asks for verbatim `commitment_text` so every number is auditable back
  to the `source_url`.
- For earnings-call transcripts (richer than 8-Ks for AI capex guidance), point the
  same extractor at transcript text instead of filing HTML.
