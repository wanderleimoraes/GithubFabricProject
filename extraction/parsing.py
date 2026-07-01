"""Shared parsing helpers for the LLM extraction layer."""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


def parse_json_array(raw: str) -> list[dict]:
    """Parse an LLM response expected to be a JSON array.

    Tolerates markdown code fences around the payload. Returns [] when the
    response isn't valid JSON or isn't a list — a malformed model reply should
    skip the filing, not crash the run.
    """
    cleaned = _FENCE.sub("", raw.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
