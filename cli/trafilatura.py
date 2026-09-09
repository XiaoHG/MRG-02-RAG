"""
网页正文抓取与 Markdown 保存工具。

本脚本使用第三方 `trafilatura` 包提取网页的主要正文内容，并将结果
保存为 UTF-8 编码的 Markdown 文件，便于后续进行医学知识库构建、文本
清洗和 RAG 数据处理。

基本用法：

    python cli/trafilatura.py
    python cli/trafilatura.py "https://example.com/article"

命令行参数：

    url
        可选的位置参数，表示需要抓取的网页地址。如果不提供，默认抓取
        `DEFAULT_URL` 中定义的示例网页。

输出规则：

    1. 输出目录固定为项目根目录下的 `output/trafilatura/`。
    2. 文件名优先使用网页标题；如果网页没有标题，则使用 URL 路径名或域名。
    3. 文件名会自动清理 Windows 不允许使用的字符，例如 `< > : " / \\ | ? *`。
    4. 文件扩展名为 `.md`。
    5. 如果目标文件已经存在，不覆盖旧文件，而是在文件名后追加三位序号，
       例如 `article.md`、`article_001.md`、`article_002.md`。
    6. 文件内容使用 UTF-8 编码保存。

依赖：

    pip install trafilatura requests

实现说明：

    当前脚本文件名为 `trafilatura.py`，与第三方包同名。为避免执行脚本时
    发生循环导入，脚本会在导入第三方包前从 `sys.path` 中移除本地 `cli`
    目录。

    首选使用 `trafilatura.fetch_url()` 抓取网页。如果该方法因代理、响应
    状态或下载器配置返回空结果，则使用 `requests` 作为回退方式，并根据
    响应编码或自动检测结果解码网页内容。

注意：

    - 目标网站可能要求登录、验证码或特殊请求头，导致网页无法抓取。
    - 网页抓取需要网络连接。
    - 本工具只负责网页正文提取和保存，不负责医学事实审核、去重或知识
      图谱三元组抽取。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_URL = "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a web page and extract its main text.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    return parser.parse_args()


def _safe_filename(name: str) -> str:
    name = unquote(name).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:180] or "untitled"


def _page_name(url: str, metadata) -> str:
    title = getattr(metadata, "title", None) if metadata else None
    if title and title.strip():
        return _safe_filename(title)

    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path.rstrip("/"))).name
    return _safe_filename(path_name or parsed.netloc or "untitled")


def _new_output_path(url: str, metadata) -> Path:
    output_dir = Path(__file__).resolve().parents[1] / "output" / "trafilatura"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = _page_name(url, metadata)
    output_path = output_dir / f"{base_name}.md"
    index = 1
    while output_path.exists():
        output_path = output_dir / f"{base_name}_{index:03d}.md"
        index += 1
    return output_path


def main() -> int:
    # This file has the same name as the third-party package. Remove the local
    # cli directory from sys.path before importing the installed package.
    script_dir = str(Path(__file__).resolve().parent)
    sys.path = [entry for entry in sys.path if str(Path(entry or ".").resolve()) != script_dir]

    from trafilatura import extract, extract_metadata, fetch_url
    import requests

    url = _parse_args().url
    downloaded = fetch_url(url)
    if downloaded is None:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MRG-Trafilatura/1.0)"},
            timeout=30,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "ascii"}:
            response.encoding = response.apparent_encoding or "utf-8"
        downloaded = response.text

    result = extract(downloaded)
    if result:
        metadata = extract_metadata(downloaded)
        output_path = _new_output_path(url, metadata)
        output_path.write_text(result.rstrip() + "\n", encoding="utf-8")
        print(f"Saved extracted content to: {output_path}")
        print(f"Output characters: {len(result)}")
    else:
        raise RuntimeError(f"Trafilatura could not extract article text from URL: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
