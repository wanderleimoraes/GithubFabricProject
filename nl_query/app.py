"""Streamlit natural-language Q&A over the Gold marts (text-to-SQL).

Flow: question + dbt schema context -> Claude -> read-only SQL -> execute on the
warehouse (DuckDB locally) -> Claude writes a short narrative + picks a chart.

Run: ``streamlit run nl_query/app.py``
"""

from __future__ import annotations

import os
import re

import duckdb
import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

try:
    from nl_query.schema_context import allowed_tables, build_schema_context
except ImportError:
    from schema_context import allowed_tables, build_schema_context  # type: ignore[no-redef]

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/sp500.duckdb")

SQL_SYSTEM_PROMPT = """You translate questions into a single read-only SQL query for a \
DuckDB warehouse. Rules:
- Use ONLY these tables: {tables}.
- Output ONLY the SQL, no prose, no markdown fences.
- SELECT statements only. Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Prefer explicit column lists and add LIMIT 1000 unless the question implies otherwise.

Schema:
{schema}"""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma)\b", re.I)


def generate_sql(client: Anthropic, question: str, schema: str) -> str:
    system = SQL_SYSTEM_PROMPT.format(tables=", ".join(sorted(allowed_tables())), schema=schema)
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
                    "Give a concise, factual 2-3 sentence answer. No preamble."
                ),
            }
        ],
    )
    return msg.content[0].text.strip()


def main() -> None:
    st.set_page_config(page_title="SP500 AI Analytics — Ask anything", layout="wide")
    st.title("📈 SP500 AI-Era Analytics — Natural-Language Q&A")
    st.caption("Ask about fundamentals, prices, or AI commitments. Backed by dbt Gold marts.")

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY is not set. See .env.example.")
        return

    client = Anthropic()
    schema = build_schema_context()
    question = st.text_input(
        "Your question",
        placeholder="e.g. Which 5 companies had the highest R&D intensity last fiscal year?",
    )

    if not question:
        with st.expander("Schema the assistant can see"):
            st.code(schema)
        return

    with st.spinner("Generating SQL..."):
        sql = generate_sql(client, question, schema)

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    if not is_safe(sql):
        st.error("Generated SQL was not a safe read-only query; aborting.")
        return

    try:
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
        con.execute("SET search_path = 'main_gold'")
        df = con.execute(sql).fetchdf()
    except Exception as exc:  # noqa: BLE001 - surface any warehouse error to the UI
        st.error(f"Query failed: {exc}")
        return

    st.subheader("Answer")
    st.write(narrate(client, question, df))

    st.subheader("Result")
    st.dataframe(df, use_container_width=True)

    # Best-effort auto chart: prefer a date/time column as x so time-series
    # questions render correctly; fall back to the first non-numeric column.
    numeric = df.select_dtypes("number").columns.tolist()
    date_cols = [c for c in df.columns if c not in numeric
                 and any(kw in c.lower() for kw in ("date", "time", "period", "year"))]
    other_cols = [c for c in df.columns if c not in numeric and c not in date_cols]
    x_col = (date_cols + other_cols or [None])[0]
    if numeric and x_col and len(df) > 1:
        st.line_chart(df.set_index(x_col)[numeric[0]])


if __name__ == "__main__":
    main()
