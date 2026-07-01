"""Read-only SQL guard for the NL Q&A app.

Kept free of Streamlit/UI imports so it can be unit-tested and reused. The LLM is
instructed to emit SELECT-only SQL; this is the belt-and-braces check before anything
touches the warehouse.
"""

from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma)\b", re.I
)


def is_safe(sql: str) -> bool:
    """True only for a query that starts as a read (SELECT/WITH) and contains no
    write/DDL keywords anywhere."""
    first_word = sql.lower().lstrip().split()[0] if sql.strip() else ""
    return first_word in ("select", "with") and not FORBIDDEN.search(sql)
