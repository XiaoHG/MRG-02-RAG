from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    content: str
    source: str
    title: str = ""
    source_type: str = "local_text"
    source_url_canonical: str = ""
    source_file: str = ""
    metadata: dict[str, Any] | None = None


def parse_markdown_document(path: str | Path) -> SourceDocument:
    document_path = Path(path).resolve()
    text = document_path.read_text(encoding="utf-8")
    fields, content = parse_front_matter(text)
    source = str(fields.get("source_url") or document_path)
    canonical = str(fields.get("source_url_canonical") or canonical_url(source))
    source_type = "web" if canonical.startswith(("http://", "https://")) else "local_text"
    document_id = stable_id("doc", canonical or str(document_path))
    title = str(fields.get("title") or document_path.stem)
    return SourceDocument(
        document_id=document_id,
        content=content,
        source=source,
        title=title,
        source_type=source_type,
        source_url_canonical=canonical,
        source_file=str(document_path),
        metadata=fields,
    )


def parse_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---"):
        return {}, markdown
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}, markdown
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^\s*([^:#]+):\s*(.*)\s*$", line)
        if not match:
            continue
        value = match.group(2).strip()
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = value.strip("\"'")
        fields[match.group(1).strip()] = str(value)
    return fields, "\n".join(lines[end + 1 :]).lstrip()


def canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    default_port = (parsed.scheme.lower(), port) in {("http", 80), ("https", 443)}
    netloc = hostname if default_port or port is None else f"{hostname}:{port}"
    return f"{parsed.scheme.lower()}://{netloc}{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}"


def stable_id(prefix: str, value: str, length: int = 24) -> str:
    return f"{prefix}:{sha256(value.encode('utf-8')).hexdigest()[:length]}"


def content_hash(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    return sha256(normalized.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
