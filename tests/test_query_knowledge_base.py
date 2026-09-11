from __future__ import annotations

import json
from pathlib import Path

from cli.query_knowledge_base import _safe_query_name, _write_query_result


def test_query_result_is_saved_as_timestamped_json(tmp_path: Path) -> None:
    query = "地方性氟中毒的主要病因是什么？ / test"
    result_path = _write_query_result(
        tmp_path,
        "chunks",
        query,
        [{"chunk_id": "chunk-1", "content": "evidence"}],
    )

    assert result_path.parent == tmp_path
    assert result_path.suffix == ".json"
    assert result_path.name.startswith("chunks_")
    assert "?" not in result_path.name
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["query"] == query
    assert payload["result_count"] == 1
    assert payload["results"][0]["chunk_id"] == "chunk-1"


def test_each_query_result_gets_a_new_file(tmp_path: Path) -> None:
    first = _write_query_result(tmp_path, "triples", "same query", [])
    second = _write_query_result(tmp_path, "triples", "same query", [])

    assert first != second
    assert first.exists()
    assert second.exists()


def test_query_name_is_readable_and_safe() -> None:
    assert _safe_query_name("  dental   fluorosis / causes  ") == "dental_fluorosis_causes"
