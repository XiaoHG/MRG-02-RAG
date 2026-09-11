from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

from cli import trafilatura


def _args(**overrides):
    values = {
        "backend": "auto",
        "region": "cn-zh",
        "safesearch": "moderate",
        "timelimit": None,
        "max_results": 20,
        "timeout": 30,
        "delay": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_run_single_skips_existing_canonical_url_before_fetch(
    tmp_path: Path, monkeypatch
) -> None:
    output_dir = tmp_path / "trafilatura"
    output_dir.mkdir()
    (output_dir / "existing.md").write_text(
        '---\nsource_url: "https://example.com/article"\n---\n\nExisting content.\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(trafilatura, "OUTPUT_DIR", output_dir)

    def fetch_url(_url: str):
        raise AssertionError("fetch_url must not run for an existing URL")

    result = trafilatura._run_single(
        "https://EXAMPLE.com:443/article#section",
        _args(),
        fetch_url,
        lambda _html: "unused",
        lambda _html: SimpleNamespace(title="unused"),
        SimpleNamespace(),
    )

    assert result == 0


def test_search_results_are_saved_and_fetch_status_is_updated(
    tmp_path: Path, monkeypatch
) -> None:
    output_dir = tmp_path / "trafilatura"
    output_dir.mkdir()
    (output_dir / "existing.md").write_text(
        '---\nsource_url: "https://example.com/existing"\n---\n\nExisting content.\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(trafilatura, "OUTPUT_DIR", output_dir)

    class FakeDDGS:
        def __init__(self, timeout: int):
            assert timeout == 30

        def text(self, *_args, **_kwargs):
            return [
                {
                    "href": "https://EXAMPLE.com:443/existing#part",
                    "title": "Existing",
                    "body": "Already downloaded",
                },
                {
                    "href": "https://example.com/new",
                    "title": "New",
                    "body": "New result",
                    "date": "2026-09-10",
                },
            ]

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))
    fetched_urls: list[str] = []

    def fetch_url(url: str):
        fetched_urls.append(url)
        return "<html>new</html>"

    result = trafilatura._run_search(
        "fluorosis",
        _args(),
        fetch_url,
        lambda _html: "Extracted content",
        lambda _html: SimpleNamespace(title="New article"),
        SimpleNamespace(),
    )

    assert result == 0
    assert fetched_urls == ["https://example.com/new"]

    json_files = list(output_dir.rglob("ddgs_search.json"))
    assert len(json_files) == 1
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["query"] == "fluorosis"
    assert payload["result_count"] == 2
    assert payload["results"][0]["fetch_status"] == "skipped_existing"
    assert payload["results"][0]["output_file"] == "existing.md"
    assert payload["results"][1]["fetch_status"] == "saved"
    assert Path(payload["results"][1]["output_file"]).name == "New article.md"
    assert Path(payload["results"][1]["output_file"]).parent.name.endswith("Z")
    assert json_files[0].parent != output_dir
    assert json_files[0].parent.name.endswith("Z")


def test_search_ddgs_deduplicates_equivalent_urls() -> None:
    class FakeDDGS:
        def __init__(self, timeout: int):
            pass

        def text(self, *_args, **_kwargs):
            return [
                {"href": "https://EXAMPLE.com:443/article#one"},
                {"href": "https://example.com/article#two"},
            ]

    results = trafilatura._search_ddgs(FakeDDGS, "fluorosis", _args())

    assert [item["url"] for item in results] == ["https://EXAMPLE.com:443/article#one"]


def test_search_ddgs_limits_content_to_200_characters() -> None:
    long_summary = "fluorosis summary " * 20

    class FakeDDGS:
        def __init__(self, timeout: int):
            pass

        def text(self, *_args, **_kwargs):
            return [{"href": "https://example.com/article", "body": long_summary}]

    results = trafilatura._search_ddgs(FakeDDGS, "fluorosis", _args())

    assert len(results[0]["content"]) == 200
    assert results[0]["content"].endswith("…")


def test_create_run_dir_uses_timestamped_child_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(trafilatura, "OUTPUT_DIR", tmp_path / "trafilatura")
    monkeypatch.setattr(trafilatura, "CURRENT_RUN_DIR", None)

    run_dir = trafilatura._create_run_dir()

    assert run_dir.parent == tmp_path / "trafilatura"
    assert run_dir.name.endswith("Z")
    assert len(run_dir.name.split("_")) == 3
    assert run_dir.is_dir()
