from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Protocol
from urllib.request import Request, urlopen
import json
import re

from catalog import SourceSpec
from storage import DatasetWriter


class Opener(Protocol):
    def __call__(self, request: Request, timeout: int) -> object: ...


@dataclass(frozen=True)
class CrawlResult:
    keyword: str
    source_name: str
    source_description: str
    url: str
    fetched_at: str
    title: str
    text: str
    content_type: str | None = None
    source_type: str = "search"
    authority_level: str = "medium"
    access_status: str = "public"
    notes: str = ""
    crawl_status: str = "ok"
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "br", "li", "section", "article", "h1", "h2", "h3"}:
            self.body_parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in {"p", "div", "li", "section", "article"}:
            self.body_parts.append("\n")

    def handle_data(self, data: str):
        text = data.strip()
        if not text or self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.body_parts.append(text + " ")


def _clean_text(text: str) -> str:
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_text(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    title = _clean_text(" ".join(parser.title_parts))
    text = _clean_text("".join(parser.body_parts))
    return title, text


def extract_document_text(content: str, content_type: str | None, url: str) -> tuple[str, str]:
    if content_type and "json" in content_type:
        try:
            data = json.loads(content)
            return url, json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return url, _clean_text(content)
    return extract_text(content)


def download_url(url: str, timeout: int = 20, opener: Opener | None = None) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; medical-knowledge-crawler/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    response = (opener or urlopen)(request, timeout=timeout)
    content_type = getattr(response, "headers", {}).get_content_type() if getattr(response, "headers", None) else None
    raw = response.read()
    charset = None
    headers = getattr(response, "headers", None)
    if headers and hasattr(headers, "get_content_charset"):
        charset = headers.get_content_charset()
    html = raw.decode(charset or "utf-8", errors="replace")
    return html, content_type


def crawl_sources(
    sources: tuple[SourceSpec, ...],
    writer: DatasetWriter,
    *,
    fetched_at: datetime | None = None,
    opener: Opener | None = None,
) -> list[CrawlResult]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    results: list[CrawlResult] = []
    for source in sources:
        records: list[CrawlResult] = []
        for url in source.urls:
            try:
                html, content_type = download_url(url, opener=opener)
                title, text = extract_document_text(html, content_type, url)
                crawl_status = "ok"
                error = ""
            except Exception as exc:
                content_type = None
                title = ""
                text = ""
                crawl_status = "failed"
                error = f"{type(exc).__name__}: {exc}"
            record = CrawlResult(
                keyword=source.keyword,
                source_name=source.name,
                source_description=source.description,
                url=url,
                fetched_at=fetched_at.isoformat(),
                title=title,
                text=text,
                content_type=content_type,
                source_type=source.source_type,
                authority_level=source.authority_level,
                access_status=source.access_status,
                notes=source.notes,
                crawl_status=crawl_status,
                error=error,
            )
            records.append(record)
            results.append(record)
        if records:
            writer.write_group(
                group_name=source.name,
                keyword=source.keyword,
                description=source.description,
                records=[record.to_dict() for record in records],
                fetched_at=fetched_at,
                source_type=source.source_type,
                authority_level=source.authority_level,
                access_status=source.access_status,
                notes=source.notes,
            )
    return results
