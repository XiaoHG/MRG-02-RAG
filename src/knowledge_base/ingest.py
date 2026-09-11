from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from knowledge_extraction.documents import chunk_text

from .metadata import SourceDocument, content_hash, parse_markdown_document, stable_id
from .store import KnowledgeBaseStore


def iter_trafilatura_documents(input_dir: str | Path) -> Iterable[SourceDocument]:
    root = Path(input_dir)
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        yield parse_markdown_document(path)


def ingest_trafilatura_documents(
    store: KnowledgeBaseStore,
    input_dir: str | Path,
    *,
    chunk_size: int = 1800,
    overlap: int = 200,
) -> dict[str, int]:
    records: list[dict[str, Any]] = []
    for document in iter_trafilatura_documents(input_dir):
        for index, chunk in enumerate(
            chunk_text(document.content, chunk_size=chunk_size, overlap=overlap, source=document.source),
            start=1,
        ):
            chunk_hash = content_hash(chunk.text)
            records.append(
                {
                    "chunk_id": stable_id("chunk", f"{document.document_id}:{index}:{chunk_hash}"),
                    "document_id": document.document_id,
                    "content": chunk.text,
                    "url": document.source,
                    "source_url_canonical": document.source_url_canonical,
                    "title": document.title,
                    "source_type": document.source_type,
                    "source_file": document.source_file,
                    "chunk_index": index,
                    "content_hash": chunk_hash,
                    "metadata": document.metadata or {},
                }
            )
    return store.upsert_chunks(records)


def iter_extraction_triples(extraction_dir: str | Path) -> Iterable[dict[str, Any]]:
    root = Path(extraction_dir)
    for csv_path in sorted(root.rglob("triples_clean.csv")):
        chunks = _load_chunks(csv_path.parent / "chunks.jsonl")
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                chunk = chunks.get(row.get("chunk_id", ""))
                yield {
                    "head_entity": row.get("head_entity", ""),
                    "relation": row.get("relation", ""),
                    "tail_entity": row.get("tail_entity", ""),
                    "source": row.get("source") or (chunk or {}).get("source", ""),
                    "chunk_id": row.get("chunk_id", ""),
                    "document_id": (chunk or {}).get("document_id", ""),
                    "content": (chunk or {}).get("text", ""),
                    "source_type": _source_type(row.get("source") or (chunk or {}).get("source", "")),
                }


def ingest_extraction_triples(store: KnowledgeBaseStore, extraction_dir: str | Path) -> dict[str, int]:
    return store.upsert_triples(iter_extraction_triples(extraction_dir))


def _load_chunks(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    chunks = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            chunks[str(item.get("chunk_id", ""))] = item
    return chunks


def _source_type(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return "web"
    suffix = Path(source).suffix.lower()
    return suffix[1:] if suffix else "local_text"
