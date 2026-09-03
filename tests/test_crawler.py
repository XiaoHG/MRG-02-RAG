from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request
import json

from mrg02_rag.catalog import CrawlConfig, build_sources, load_config
from mrg02_rag.crawler import crawl_sources, extract_text
from mrg02_rag.storage import DatasetWriter


def test_load_config_and_build_sources(tmp_path: Path) -> None:
    config_path = tmp_path / "crawl_config.json"
    config_path.write_text(
        json.dumps(
            {
                "keywords": ["\u6c1f\u6591\u7259", "\u6c1f\u9aa8\u75c7", "\u6c1f\u4e2d\u6bd2"],
                "url_templates": ["https://example.com/search?q={keyword}"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    sources = build_sources(config)

    assert [source.keyword for source in sources] == ["\u6c1f\u6591\u7259", "\u6c1f\u9aa8\u75c7", "\u6c1f\u4e2d\u6bd2"]
    assert sources[0].urls == ("https://example.com/search?q=%E6%B0%9F%E6%96%91%E7%89%99",)


def test_extract_text_returns_title_and_body() -> None:
    html = """
    <html>
      <head><title>Fluorosis Guide</title></head>
      <body><h1>\u6c1f\u6591\u7259</h1><p>Clinical signs</p><script>ignore()</script></body>
    </html>
    """
    title, text = extract_text(html)
    assert title == "Fluorosis Guide"
    assert "\u6c1f\u6591\u7259" in text
    assert "ignore" not in text


def test_crawl_sources_writes_timestamped_dataset(tmp_path: Path) -> None:
    def opener(request: Request, timeout: int):
        class Response:
            def __init__(self) -> None:
                self.headers = type(
                    "H",
                    (),
                    {
                        "get_content_type": lambda self: "text/html",
                        "get_content_charset": lambda self: "utf-8",
                    },
                )()

            def read(self) -> bytes:
                return b"<html><head><title>Doc</title></head><body><p>Content</p></body></html>"

        return Response()

    writer = DatasetWriter(tmp_path)
    sources = build_sources(CrawlConfig(keywords=("\u6c1f\u6591\u7259",), url_templates=("https://example.com/a?keyword={keyword}",)))
    results = crawl_sources(
        sources,
        writer,
        fetched_at=datetime(2026, 9, 3, 2, 0, 0, tzinfo=timezone.utc),
        opener=opener,
    )

    assert len(results) == 1
    group_dir = tmp_path / "\u6c1f\u6591\u7259" / "20260903_020000"
    assert (group_dir / "README.md").exists()
    manifest = json.loads((group_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["keyword"] == "\u6c1f\u6591\u7259"
    assert manifest["record_count"] == 1
    lines = (group_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["title"] == "Doc"
