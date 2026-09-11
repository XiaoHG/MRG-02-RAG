from __future__ import annotations

from pathlib import Path

from knowledge_extraction.documents import chunk_text, load_document_chunks


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


def test_load_document_chunks_extracts_html_visible_text(tmp_path: Path) -> None:
    html_path = tmp_path / "article.html"
    html_path.write_text(
        "<html><head><style>.hidden {}</style></head>"
        "<body><h1>氟中毒</h1><script>ignore this</script>"
        "<p>临床表现和预防。</p></body></html>",
        encoding="utf-8",
    )

    chunks = load_document_chunks(html_path, chunk_size=100, overlap=20)

    assert len(chunks) == 1
    assert "氟中毒" in chunks[0].text
    assert "临床表现和预防" in chunks[0].text
    assert "ignore this" not in chunks[0].text


def test_load_document_chunks_supports_common_text_files_and_gb18030(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_bytes("地方性氟中毒".encode("gb18030"))
    markdown_path = tmp_path / "notes.md"
    markdown_path.write_text("# 诊断\n氟斑牙", encoding="utf-8")

    chunks = load_document_chunks(text_path) + load_document_chunks(markdown_path)

    assert "地方性氟中毒" in chunks[0].text
    assert "氟斑牙" in chunks[1].text
