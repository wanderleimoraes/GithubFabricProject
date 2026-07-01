"""Unit tests for the Wikipedia timeline chunker."""

from ingestion.ai_events_wikipedia import _chunks


def test_short_text_single_chunk():
    assert _chunks("one paragraph") == ["one paragraph"]


def test_splits_on_paragraphs_within_size():
    text = "para one\npara two\npara three"
    chunks = _chunks(text, size=15)
    # Each chunk stays under/near the size cap and no paragraph is lost.
    assert all(len(c) <= 20 for c in chunks)
    joined = "\n".join(chunks)
    for p in ("para one", "para two", "para three"):
        assert p in joined


def test_blank_lines_dropped():
    chunks = _chunks("a\n\n\nb", size=100)
    assert chunks == ["a\nb"]


def test_no_content_loss_on_large_text():
    paragraphs = [f"paragraph number {i}" for i in range(50)]
    chunks = _chunks("\n".join(paragraphs), size=200)
    joined = "\n".join(chunks)
    assert all(p in joined for p in paragraphs)
    assert len(chunks) > 1
