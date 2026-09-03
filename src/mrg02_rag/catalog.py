from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from urllib.parse import quote_plus


@dataclass(frozen=True)
class SourceSpec:
    keyword: str
    name: str
    description: str
    urls: tuple[str, ...]


@dataclass(frozen=True)
class CrawlConfig:
    keywords: tuple[str, ...]
    url_templates: tuple[str, ...]


def default_config() -> CrawlConfig:
    return CrawlConfig(
        keywords=("\u6c1f\u6591\u7259", "\u6c1f\u9aa8\u75c7", "\u6c1f\u4e2d\u6bd2"),
        url_templates=(
            "https://duckduckgo.com/?q={keyword}",
            "https://www.baidu.com/s?wd={keyword}",
        ),
    )


def load_config(path: str | Path) -> CrawlConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return CrawlConfig(
        keywords=tuple(data.get("keywords", [])),
        url_templates=tuple(data.get("url_templates", [])),
    )


def build_sources(config: CrawlConfig) -> tuple[SourceSpec, ...]:
    sources: list[SourceSpec] = []
    for keyword in config.keywords:
        encoded_keyword = quote_plus(keyword)
        urls = tuple(
            template.format(
                keyword=encoded_keyword,
                keyword_raw=keyword,
                keyword_encoded=encoded_keyword,
                query=encoded_keyword,
                query_raw=keyword,
                query_encoded=encoded_keyword,
            )
            for template in config.url_templates
        )
        sources.append(
            SourceSpec(
                keyword=keyword,
                name=keyword,
                description=f"{keyword}\u76f8\u5173\u533b\u5b66\u77e5\u8bc6\u4e0e\u4e34\u5e8a\u8d44\u6599",
                urls=urls,
            )
        )
    return tuple(sources)


def default_sources() -> tuple[SourceSpec, ...]:
    return build_sources(default_config())
