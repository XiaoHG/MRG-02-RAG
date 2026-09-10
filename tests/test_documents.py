from __future__ import annotations

from documents import chunk_text


def test_chunk_text_uses_overlap_and_source_ids() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=6, overlap=2, source="paper.txt")

    assert [chunk.text for chunk in chunks] == ["abcdefghij"[:6], "efghij"]
    assert [chunk.chunk_id for chunk in chunks] == ["paper-0001", "paper-0002"]
    assert all(chunk.source == "paper.txt" for chunk in chunks)


def test_chunk_text_rejects_invalid_overlap() -> None:
    try:
        chunk_text("abc", chunk_size=3, overlap=3)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("expected ValueError")
