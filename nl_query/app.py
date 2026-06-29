"""Streamlit natural-language Q&A over the Gold marts (text-to-SQL).

Flow: question + dbt schema context -> Claude -> read-only SQL -> execute on the
warehouse (DuckDB locally) -> Claude writes a short narrative + picks a chart.

Run: ``streamlit run nl_query/app.py``
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

try:
    from nl_query.ontology import build_ontology_context
    from nl_query.schema_context import allowed_tables, build_schema_context
except ImportError:
    from ontology import build_ontology_context  # type: ignore[no-redef]
    from schema_context import allowed_tables, build_schema_context  # type: ignore[no-redef]

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/sp500.duckdb")
SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read config from Streamlit secrets first, then environment (.env locally)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 - no secrets file in local dev
        pass
    return os.getenv(name, default)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to the local DuckDB warehouse if present (local dev), else load the
    bundled sample Parquet marts into an in-memory DB (deployed app)."""
    local_db = Path(DUCKDB_PATH)
    if local_db.exists():
        con = duckdb.connect(str(local_db), read_only=True)
        con.execute("SET search_path = 'main_gold'")
        return con
    con = duckdb.connect(":memory:")
    for pq in sorted(SAMPLE_DIR.glob("*.parquet")):
        con.execute(
            f'CREATE TABLE "{pq.stem}" AS SELECT * FROM read_parquet(?)', [pq.as_posix()]
        )
    return con


def check_password() -> bool:
    """Gate the app behind a shared password (set APP_PASSWORD in Streamlit secrets).
    If no password is configured (local dev), the app is open."""
    expected = get_secret("APP_PASSWORD")
    if not expected:
        return True
    if st.session_state.get("auth_ok"):
        return True
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == expected:
            st.session_state["auth_ok"] = True
            return True
        st.error("Incorrect password.")
    return False

SQL_SYSTEM_PROMPT = """You translate questions into a single read-only SQL query for a \
DuckDB warehouse. Rules:
- Use ONLY these tables: {tables}.
- Output ONLY the SQL, no prose, no markdown fences.
- SELECT statements only. Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Prefer explicit column lists and add LIMIT 1000 unless the question implies otherwise.
- Follow the semantic layer below: use its relationships for joins and its metric
  glossary for any business term (margins, growth, intensity, outperform, etc.).

Schema:
{schema}

Semantic layer:
{ontology}"""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma)\b", re.I)


def generate_sql(client: Anthropic, question: str, schema: str) -> str:
    system = SQL_SYSTEM_PROMPT.format(
        tables=", ".join(sorted(allowed_tables())),
        schema=schema,
        ontology=build_ontology_context(),
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    sql = msg.content[0].text.strip()
    return re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.MULTILINE).strip()


def is_safe(sql: str) -> bool:
    first_word = sql.lower().lstrip().split()[0] if sql.strip() else ""
    return first_word in ("select", "with") and not FORBIDDEN.search(sql)


def narrate(client: Anthropic, question: str, df: pd.DataFrame) -> str:
    preview = df.head(20).to_markdown(index=False)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\nResult (first rows):\n{preview}\n\n"
                    "Answer in 2-3 sentences using ONLY the numbers and rows shown in "
                    "the result above. Do not add facts, figures, or company details that "
                    "aren't in the data. If the result is empty, say there is no matching "
                    "data. No preamble."
                ),
            }
        ],
    )
    return msg.content[0].text.strip()


def render_reference_sidebar() -> None:
    """Always-visible reference so users know what they can ask."""
    with st.sidebar:
        st.header("💡 What you can ask")
        st.markdown(
            "**Try these examples:**\n"
            "- Top 15 companies by R&D spend over the last 5 years\n"
            "- Total revenue by sector\n"
            "- Apple's year-over-year revenue growth\n"
            "- Companies with the highest net margin last year\n"
            "- Total AI committed by sector\n"
            "- Most significant AI partnership facts in the last 5 years, with sources\n"
            "- Which companies outperformed their sector on the latest trading day\n"
            "- Do companies with higher R&D intensity make larger AI commitments?"
        )
        st.markdown(
            "**Keywords it understands:**\n"
            "- **Companies / sectors:** ticker, company name, GICS sector\n"
            "- **Fundamentals:** revenue, net income, R&D expense, capex, net margin, "
            "R&D intensity, EPS\n"
            "- **Prices:** close, adjusted close, daily return, 50/200-day moving average\n"
            "- **AI commitments:** committed amount (USD), confidence, vs revenue\n"
            "- **AI material facts:** partnerships, products, capex, acquisitions, "
            "research, with source links\n"
            "- **Time:** last N years, latest, year-over-year (uses real dates)"
        )
        st.caption("Tip: it generates SQL — check the **Generated SQL** to verify any answer.")


def main() -> None:
    st.set_page_config(page_title="SP500 AI Analytics — Ask anything", layout="wide")
    st.title("📈 SP500 AI-Era Analytics — Natural-Language Q&A")
    st.caption("Ask about fundamentals, prices, or AI commitments. Backed by dbt Gold marts.")
    render_reference_sidebar()

    if not check_password():
        return

    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY is not set. See .env.example / Streamlit secrets.")
        return

    max_questions = int(get_secret("MAX_QUESTIONS_PER_SESSION", "20") or "20")
    asked = st.session_state.get("q_count", 0)
    if asked >= max_questions:
        st.warning(f"Session limit reached ({max_questions} questions). Refresh to reset.")
        return

    client = Anthropic(api_key=api_key)
    schema = build_schema_context()
    question = st.text_input(
        "Your question",
        placeholder="e.g. Which 5 companies had the highest R&D intensity last fiscal year?",
    )

    if not question:
        with st.expander("Schema the assistant can see"):
            st.code(schema)
        return

    st.session_state["q_count"] = asked + 1

    with st.spinner("Generating SQL..."):
        sql = generate_sql(client, question, schema)

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    if not is_safe(sql):
        st.error("Generated SQL was not a safe read-only query; aborting.")
        return

    try:
        con = get_connection()
        df = con.execute(sql).fetchdf()
    except Exception as exc:  # noqa: BLE001 - surface any warehouse error to the UI
        st.error(f"Query failed: {exc}")
        return

    st.subheader("Answer")
    st.write(narrate(client, question, df))
    st.caption("⚠️ AI-generated from the query above. Check the **Generated SQL** and "
               "**Result** below to verify — the answer is only as correct as the query.")

    st.subheader("Result")
    st.dataframe(df, use_container_width=True)

    # Chart controls — let the user pick axes and chart type.
    numeric = df.select_dtypes("number").columns.tolist()
    if numeric and len(df) > 1:
        st.subheader("Chart")
        date_cols = [c for c in df.columns if c not in numeric
                     and any(kw in c.lower() for kw in ("date", "time", "period", "year"))]
        other_cols = [c for c in df.columns if c not in numeric and c not in date_cols]
        default_x = (date_cols + other_cols or [df.columns[0]])[0]

        col1, col2, col3 = st.columns(3)
        CHART_TYPES = ["Line", "Bar", "Area", "Scatter", "Histogram", "Pie"]
        chart_type = col1.selectbox("Chart type", CHART_TYPES, index=0)

        if chart_type == "Scatter":
            x_col = col2.selectbox("X axis (numeric)", numeric, index=min(1, len(numeric) - 1))
            y_col = col3.selectbox("Y axis (numeric)", numeric, index=0)
        elif chart_type == "Histogram":
            x_col = col2.selectbox("Column", numeric, index=0)
            y_col = None
        else:
            all_cols = df.columns.tolist()
            x_col = col2.selectbox("X axis / Labels", all_cols,
                                   index=all_cols.index(default_x))
            y_col = col3.selectbox("Y axis / Values", numeric, index=0)

        def _xy():
            # X and Y must be different columns; set_index moves X out of the frame.
            if not y_col or x_col == y_col or y_col not in df.columns:
                st.info("Pick different columns for the X and Y axes to draw this chart.")
                return None
            return df.set_index(x_col)[[y_col]]

        try:
            if chart_type == "Line":
                data = _xy()
                if data is not None:
                    st.line_chart(data)
            elif chart_type == "Bar":
                data = _xy()
                if data is not None:
                    st.bar_chart(data)
            elif chart_type == "Area":
                data = _xy()
                if data is not None:
                    st.area_chart(data)
            elif chart_type == "Scatter":
                st.plotly_chart(px.scatter(df, x=x_col, y=y_col), use_container_width=True)
            elif chart_type == "Histogram":
                st.plotly_chart(px.histogram(df, x=x_col), use_container_width=True)
            else:  # Pie
                st.plotly_chart(px.pie(df, names=x_col, values=y_col), use_container_width=True)
        except Exception as exc:  # noqa: BLE001 - never crash the app on a chart axis mismatch
            st.warning(f"Couldn't draw this chart for the selected columns ({exc}). "
                       "Try different axes or another chart type.")


if __name__ == "__main__":
    main()
