from __future__ import annotations

import json
from pathlib import Path

import pytest

lancedb = pytest.importorskip("lancedb")

from knowledge_base.embeddings import HashEmbeddingProvider
from knowledge_base.ingest import ingest_extraction_triples, ingest_trafilatura_documents
from knowledge_base.metadata import parse_markdown_document
from knowledge_base.store import CHUNKS_TABLE, TRIPLES_TABLE, KnowledgeBaseStore


def make_store(tmp_path: Path) -> KnowledgeBaseStore:
    return KnowledgeBaseStore(
        tmp_path / "LanceDB",
        embedding_provider=HashEmbeddingProvider(dimension=16),
    ).connect()


def test_store_initializes_two_tables_and_deduplicates_records(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.initialize()

    assert set(store._db.list_tables().tables) == {CHUNKS_TABLE, TRIPLES_TABLE}
    chunk = {
        "content": "Dental fluorosis is associated with excess fluoride exposure.",
        "source": "https://example.org/article",
        "title": "Fluorosis",
        "source_type": "web",
    }
    assert store.upsert_chunks([chunk]) == {"added": 1, "skipped": 0}
    assert store.upsert_chunks([chunk]) == {"added": 0, "skipped": 1}
    assert store.count(CHUNKS_TABLE) == 1

    triple = {
        "head_entity": "Dental fluorosis",
        "relation": "caused_by",
        "tail_entity": "fluoride exposure",
        "chunk_id": "chunk-1",
        "content": chunk["content"],
        "source": chunk["source"],
        "review_status": "pending",
    }
    assert store.upsert_triples([triple]) == {"added": 1, "skipped": 0}
    assert store.upsert_triples([triple]) == {"added": 0, "skipped": 1}
    assert store.count(TRIPLES_TABLE) == 1


def test_queries_filter_and_return_source_evidence(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.upsert_chunks(
        [
            {
                "content": "Approved clinical evidence.",
                "source": "https://example.org/a",
                "title": "Clinical source",
                "source_type": "web",
            }
        ]
    )
    store.upsert_triples(
        [
            {
                "head_entity": "Condition",
                "relation": "caused_by",
                "tail_entity": "Exposure",
                "chunk_id": "chunk-1",
                "content": "Approved clinical evidence.",
                "source": "https://example.org/a",
                "title": "Clinical source",
                "source_type": "web",
                "review_status": "approved",
            },
            {
                "head_entity": "Condition",
                "relation": "has_symptom",
                "tail_entity": "Pain",
                "chunk_id": "chunk-2",
                "content": "Pending evidence.",
                "source": "notes.txt",
                "review_status": "pending",
            },
        ]
    )

    rows = store.search_triples(
        store.embed("Condition caused_by Exposure"),
        relation="caused_by",
        review_status="approved",
        limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "https://example.org/a"
    assert rows[0]["content"] == "Approved clinical evidence."
    assert rows[0]["title"] == "Clinical source"
    assert "_distance" in rows[0]

    store.update_triple_review_status(rows[0]["triple_id"], "rejected", confidence=0.1)
    assert store.search_triples(review_status="approved", limit=10) == []


def test_markdown_ingestion_is_incremental_and_preserves_front_matter(tmp_path: Path) -> None:
    source_dir = tmp_path / "output" / "trafilatura" / "20260911_120000"
    source_dir.mkdir(parents=True)
    markdown_path = source_dir / "article.md"
    markdown_path.write_text(
        '---\nsource_url: "https://example.org/article"\n'
        'source_url_canonical: "https://example.org/article"\n'
        'title: "Clinical article"\n---\n\n'
        "Dental fluorosis is associated with excess fluoride exposure.",
        encoding="utf-8",
    )

    document = parse_markdown_document(markdown_path)
    assert document.title == "Clinical article"
    assert document.source_type == "web"
    assert "source_url:" not in document.content

    store = make_store(tmp_path)
    first = ingest_trafilatura_documents(store, tmp_path / "output" / "trafilatura")
    second = ingest_trafilatura_documents(store, tmp_path / "output" / "trafilatura")
    assert first["added"] == 1
    assert second["added"] == 0
    assert store.count(CHUNKS_TABLE) == 1


def test_extraction_triples_ingestion_uses_chunk_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "output" / "extraction" / "20260911_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "chunks.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "article-0001",
                "text": "Condition is caused by exposure.",
                "source": "https://example.org/article",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "triples_clean.csv").write_text(
        "head_entity,relation,tail_entity,source,chunk_id\n"
        "Condition,caused_by,Exposure,https://example.org/article,article-0001\n",
        encoding="utf-8",
    )
    store = make_store(tmp_path)
    result = ingest_extraction_triples(store, tmp_path / "output" / "extraction")
    assert result == {"added": 1, "skipped": 0}
    row = store.search_triples(relation="caused_by", limit=1)[0]
    assert row["chunk_id"] == "article-0001"
    assert row["content"] == "Condition is caused by exposure."
