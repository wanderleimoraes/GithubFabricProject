"""Unit tests for the NL Q&A read-only SQL guard."""

from nl_query.sql_guard import is_safe


def test_select_is_safe():
    assert is_safe("SELECT * FROM mart_prices LIMIT 10")


def test_cte_is_safe():
    assert is_safe("WITH x AS (SELECT 1) SELECT * FROM x")


def test_leading_whitespace_ok():
    assert is_safe("   \n  select 1")


def test_insert_rejected():
    assert not is_safe("INSERT INTO mart_prices VALUES (1)")


def test_drop_hidden_in_select_rejected():
    assert not is_safe("SELECT 1; DROP TABLE mart_prices")


def test_pragma_rejected():
    assert not is_safe("PRAGMA database_list")


def test_word_boundary_not_overzealous():
    # Column/table names *containing* forbidden words are fine (e.g. created_at).
    assert is_safe("SELECT created_at FROM mart_ai_events")


def test_empty_rejected():
    assert not is_safe("")
