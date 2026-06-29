# Deploying the NL Q&A app (Streamlit Community Cloud)

The natural-language Q&A app (`nl_query/app.py`) is the report's "ask it yourself"
endpoint. This guide deploys it for **free** to a public URL you can wire into the
Power BI launchpad button.

## How it works when deployed

- **Data:** the deployed container has no warehouse, so the app loads the bundled
  Parquet marts in `nl_query/sample_data/` into in-memory DuckDB. (Locally, if
  `data/sp500.duckdb` exists, it uses that instead.) Refresh the bundle anytime with
  `python -m scripts.export_nl_query_sample` and commit the updated files.
- **Engine:** Claude turns questions into SQL, grounded by `nl_query/ontology.py`.
- **Protection:** a shared **password gate** (`APP_PASSWORD`) and a **per-session
  question cap** (`MAX_QUESTIONS_PER_SESSION`) keep your Anthropic key from being
  drained by the public.

## One-time: refresh the bundled data (optional)

After ingesting real data and running `dbt build --target duckdb`:
```powershell
python -m scripts.export_nl_query_sample
git add nl_query/sample_data/*.parquet
git commit -m "Refresh NL Q&A sample data"
git push origin claude/sp500-data-portfolio-sinj32
```

## Deploy steps

1. Make sure your branch is pushed to GitHub (it is).
2. Go to **https://share.streamlit.io** and sign in with GitHub. Authorize access to
   the `wanderleimoraes/GithubFabricProject` repo.
3. Click **Create app** → **Deploy a public app from GitHub**.
4. Fill in:
   - **Repository:** `wanderleimoraes/GithubFabricProject`
   - **Branch:** `claude/sp500-data-portfolio-sinj32` (or `main` after you merge)
   - **Main file path:** `nl_query/app.py`
5. Click **Advanced settings → Secrets** and paste (your real values):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   APP_PASSWORD = "choose-a-password"
   MAX_QUESTIONS_PER_SESSION = "20"
   ```
6. Click **Deploy**. First build takes a few minutes (installs `requirements.txt`).
7. When it's live you'll get a URL like
   `https://<something>.streamlit.app` — that's your public endpoint.

## Wire it into the Power BI launchpad

On the **NL Q&A** report page, select the CTA button → **Format → Action → Web URL**
→ paste the `https://...streamlit.app` URL (replacing the `localhost:8501` placeholder).
Save and push.

## Local testing with secrets

Copy the template and fill it in (the real file is git-ignored):
```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run nl_query/app.py
```
With no `APP_PASSWORD` set locally, the gate is bypassed for convenience.

## Notes & gotchas

- **Requirements:** Streamlit Cloud installs the repo-root `requirements.txt`. It
  includes dbt adapters the app doesn't strictly need (slower first build, still works).
- **Cost:** every question calls Claude on your key. The password + session cap are
  your guardrails; rotate `APP_PASSWORD` if you share it widely.
- **Data freshness:** the public app shows the committed snapshot in
  `nl_query/sample_data/`, not live Databricks — so it keeps working for free even
  after the Azure teardown on 2026-07-24.
