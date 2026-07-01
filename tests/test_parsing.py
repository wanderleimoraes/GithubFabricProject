"""Unit tests for the LLM-response parsing shared by all extractors."""

from extraction.parsing import parse_json_array


def test_plain_json_array():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_fenced_json_array():
    raw = '```json\n[{"headline": "x", "amount_usd": null}]\n```'
    assert parse_json_array(raw) == [{"headline": "x", "amount_usd": None}]


def test_fence_without_language_tag():
    assert parse_json_array("```\n[]\n```") == []


def test_invalid_json_returns_empty():
    assert parse_json_array("Sorry, I cannot help with that.") == []


def test_non_list_json_returns_empty():
    # A model that answers with an object instead of an array must not crash the run.
    assert parse_json_array('{"a": 1}') == []


def test_empty_string():
    assert parse_json_array("") == []
