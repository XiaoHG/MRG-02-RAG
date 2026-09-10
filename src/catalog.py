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
    source_type: str = "search"
    authority_level: str = "medium"
    access_status: str = "public"
    notes: str = ""


@dataclass(frozen=True)
class CrawlConfig:
    keywords: tuple[str, ...]
    url_templates: tuple[str, ...]
    source_groups: tuple[dict[str, object], ...] = ()
    restricted_resources: tuple[dict[str, object], ...] = ()


def default_config() -> CrawlConfig:
    return CrawlConfig(
        keywords=("氟斑牙", "氟骨症", "氟中毒"),
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
        source_groups=tuple(data.get("source_groups", [])),
        restricted_resources=tuple(data.get("restricted_resources", [])),
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
        if not urls:
            continue
        sources.append(
            SourceSpec(
                keyword=keyword,
                name=keyword,
                description=f"{keyword}相关医学知识与临床资料",
                urls=urls,
            )
        )
    for group in config.source_groups:
        keywords = tuple(str(item) for item in group.get("keywords", config.keywords))
        templates = tuple(str(item) for item in group.get("url_templates", []))
        static_urls = tuple(str(item) for item in group.get("urls", []))
        for keyword in keywords:
            encoded_keyword = quote_plus(keyword)
            urls = static_urls + tuple(
                template.format(
                    keyword=encoded_keyword,
                    keyword_raw=keyword,
                    keyword_encoded=encoded_keyword,
                    query=encoded_keyword,
                    query_raw=keyword,
                    query_encoded=encoded_keyword,
                )
                for template in templates
            )
            if not urls:
                continue
            name = str(group.get("name", keyword))
            group_name = f"{name}-{keyword}" if len(keywords) > 1 or templates else name
            sources.append(
                SourceSpec(
                    keyword=keyword,
                    name=group_name,
                    description=str(group.get("description", f"{keyword} related medical source")),
                    urls=urls,
                    source_type=str(group.get("source_type", "reference")),
                    authority_level=str(group.get("authority_level", "medium")),
                    access_status=str(group.get("access_status", "public")),
                    notes=str(group.get("notes", "")),
                )
            )
    return tuple(sources)


def default_sources() -> tuple[SourceSpec, ...]:
    return build_sources(default_config())
