"""
网页正文抓取、论文检索与 Markdown 保存工具。

本脚本提供两种工作模式：

1. 单网页抓取
   直接传入一个网页 URL，使用 Trafilatura 提取网页正文。

2. DDGS + Trafilatura 批量论文采集
   通过 DDGS 检索论文或医学主题相关网页，再逐条抓取搜索结果并使用
   Trafilatura 提取正文。该模式用于先跑通“检索 -> 网页抓取 -> 正文提取
   -> Markdown 保存”的最小闭环，后续可以替换为 SearXNG。每个成功提取的网页单独保存为
   一个 Markdown 文件，适合批量构建医学知识库的原始资料。

单网页模式：

    python cli/trafilatura.py
    python cli/trafilatura.py "https://example.com/article"

批量检索模式：

    python cli/trafilatura.py \
        --query "地方性氟中毒 发病机制" \
        --backend "auto" \
        --max-results 20

PowerShell 示例：

    python .\\cli\\trafilatura.py `
        --query "fluorosis pathogenesis" `
        --backend "auto" `
        --region "cn-zh" `
        --max-results 50

批量检索参数：

    --query, -q
        DDGS 检索词。提供该参数后进入批量检索模式。

    --backend
        DDGS 搜索后端，默认是 `auto`。也可以指定后端名称或逗号分隔的后端。

    --max-results
        最多处理的搜索结果数量，默认 20。

    --region
        DDGS 搜索区域，默认是 `cn-zh`。
输出规则：

    1. 输出目录固定为项目根目录下的 `output/trafilatura/`。
    2. 文件名优先使用网页标题，其次使用 DDGS 返回的标题，最后使用
       URL 路径名或域名。
    3. 文件名会自动清理 Windows 不允许使用的字符。
    4. 文件扩展名为 `.md`。
    5. 不覆盖已有文件。同名时自动追加三位序号，例如
       `article.md`、`article_001.md`、`article_002.md`。
    6. 文件内容使用 UTF-8 编码。
    7. 批量模式的 Markdown 文件开头会保存来源 URL、搜索词、搜索结果标题、
       摘要和发布时间等元数据，方便后续追溯。

注意事项：

    - DDGS 底层搜索源可能出现验证码、访问限制或暂时不可用。
    - 搜索结果中的 PDF、登录页、验证码页和 JavaScript 应用可能无法提取正文。
    - 论文全文通常受版权、数据库权限和网站 robots 规则限制，请遵守目标
      网站和数据源的使用条款。
    - 本工具只负责抓取、正文提取和保存，不负责医学事实审核、去重或三元组抽取。

依赖：

    pip install ddgs trafilatura requests

实现说明：

    当前脚本文件名为 `trafilatura.py`，与第三方包同名。为避免执行脚本时
    发生循环导入，脚本会在导入第三方包前从 `sys.path` 中移除本地 `cli`
    目录。
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_URL = "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch web pages or search with DDGS and extract content with Trafilatura."
    )
    parser.add_argument("url", nargs="?", help="URL for single-page extraction.")
    parser.add_argument("--query", "-q", help="DDGS query for batch collection.")
    parser.add_argument("--backend", default="auto", help="DDGS backend name(s), default: auto.")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--region", default="cn-zh", help="DDGS search region, default: cn-zh.")
    parser.add_argument("--safesearch", choices=("on", "moderate", "off"), default="moderate")
    parser.add_argument("--timelimit", choices=("d", "w", "m", "y"), help="Limit results by time.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.0)
    return parser.parse_args()


def _safe_filename(name: str) -> str:
    name = unquote(name).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:180] or "untitled"


def _page_name(url: str, metadata=None, fallback_title: str | None = None) -> str:
    title = getattr(metadata, "title", None) if metadata else None
    if title and title.strip():
        return _safe_filename(title)
    if fallback_title and fallback_title.strip():
        return _safe_filename(fallback_title)

    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path.rstrip("/"))).name
    return _safe_filename(path_name or parsed.netloc or "untitled")


def _new_output_path(url: str, metadata=None, fallback_title: str | None = None) -> Path:
    output_dir = Path(__file__).resolve().parents[1] / "output" / "trafilatura"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = _page_name(url, metadata, fallback_title)
    output_path = output_dir / f"{base_name}.md"
    index = 1
    while output_path.exists():
        output_path = output_dir / f"{base_name}_{index:03d}.md"
        index += 1
    return output_path


def _fetch_html(url: str, fetch_url, requests, timeout: int) -> str:
    downloaded = fetch_url(url)
    if downloaded is not None:
        return downloaded

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; MRG-Trafilatura/1.0)"},
        timeout=timeout,
    )
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "ascii"}:
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _metadata_value(metadata, name: str) -> str:
    value = getattr(metadata, name, None) if metadata else None
    return str(value).strip() if value else ""


def _format_metadata(metadata: dict) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if value:
            escaped = str(value).replace("\r", " ").replace("\n", " ").replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def _save_extraction(
    url: str,
    result: str,
    extract_metadata,
    downloaded: str,
    fallback_title: str | None = None,
    source_metadata: dict | None = None,
) -> Path:
    metadata = extract_metadata(downloaded)
    output_path = _new_output_path(url, metadata, fallback_title)
    page_metadata = {
        "title": _metadata_value(metadata, "title") or fallback_title or "",
        "author": _metadata_value(metadata, "author"),
        "date": _metadata_value(metadata, "date"),
        "sitename": _metadata_value(metadata, "sitename"),
        "source_url": url,
    }
    if source_metadata:
        page_metadata.update(source_metadata)

    content = f"{_format_metadata(page_metadata)}\n\n{result.rstrip()}\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _search_ddgs(DDGS, query: str, args) -> list[dict]:
    try:
        raw_results = DDGS(timeout=args.timeout).text(
            query,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            max_results=args.max_results,
            page=1,
            backend=args.backend,
        )
    except Exception as exc:
        raise RuntimeError(f"DDGS search failed: {exc}") from exc

    results = []
    seen_urls = set()
    for item in raw_results:
        url = item.get("href") or item.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "content": item.get("body") or item.get("content") or "",
                "publishedDate": item.get("date") or "",
            }
        )
    return results


def _run_single(url: str, args, fetch_url, extract, extract_metadata, requests) -> int:
    downloaded = _fetch_html(url, fetch_url, requests, args.timeout)
    result = extract(downloaded)
    if not result:
        raise RuntimeError(f"Trafilatura could not extract article text from URL: {url}")

    output_path = _save_extraction(url, result, extract_metadata, downloaded)
    print(f"Saved extracted content to: {output_path}")
    print(f"Output characters: {len(result)}")
    return 0


def _run_search(query: str, args, fetch_url, extract, extract_metadata, requests) -> int:
    if args.max_results <= 0:
        raise ValueError("--max-results must be greater than 0.")
    from ddgs import DDGS

    candidates = _search_ddgs(DDGS, query, args)
    print(f"DDGS returned {len(candidates)} unique results.")
    success_count = 0
    failure_count = 0
    for index, item in enumerate(candidates, start=1):
        url = item["url"]
        title = item.get("title") or ""
        print(f"[{index}/{len(candidates)}] fetching {title or url}", file=sys.stderr, flush=True)
        try:
            downloaded = _fetch_html(url, fetch_url, requests, args.timeout)
            result = extract(downloaded)
            if not result:
                raise RuntimeError("no article text extracted")

            source_metadata = {
                "search_query": query,
                "search_title": title,
                "search_snippet": item.get("content") or "",
                "search_published_date": item.get("publishedDate") or "",
            }
            output_path = _save_extraction(
                url,
                result,
                extract_metadata,
                downloaded,
                fallback_title=title,
                source_metadata=source_metadata,
            )
            print(f"Saved [{index}/{len(candidates)}]: {output_path}")
            success_count += 1
        except Exception as exc:
            failure_count += 1
            print(f"Skipped [{index}/{len(candidates)}] {url}: {exc}", file=sys.stderr)
        if args.delay > 0 and index < len(candidates):
            time.sleep(args.delay)

    print(f"Finished: {success_count} saved, {failure_count} skipped.")
    return 0 if success_count or not candidates else 1


def main() -> int:
    args = _parse_args()

    if args.url and args.query:
        raise ValueError("Use either a URL or --query, not both.")
    if not args.url and not args.query:
        args.url = DEFAULT_URL

    # This file has the same name as the third-party package. Remove the local
    # cli directory from sys.path before importing the installed package.
    script_dir = str(Path(__file__).resolve().parent)
    sys.path = [entry for entry in sys.path if str(Path(entry or ".").resolve()) != script_dir]

    from trafilatura import extract, extract_metadata, fetch_url
    import requests

    if args.query:
        return _run_search(args.query, args, fetch_url, extract, extract_metadata, requests)
    return _run_single(args.url, args, fetch_url, extract, extract_metadata, requests)


if __name__ == "__main__":
    raise SystemExit(main())
