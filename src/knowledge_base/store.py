from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .embeddings import EmbeddingProvider, create_embedding_provider
from .metadata import content_hash, now_iso, stable_id


CHUNKS_TABLE = "knowledge_chunks"
TRIPLES_TABLE = "knowledge_triples"


class KnowledgeBaseStore:
    """LanceDB storage with application-level idempotency and source traceability."""

    def __init__(
        self,
        db_path: str | Path = "LanceDB",
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self._db = None
        self._tables: dict[str, Any] = {}

    def connect(self) -> "KnowledgeBaseStore":
        try:
            import lancedb
        except ImportError as exc:
            raise RuntimeError(
                "LanceDB is required for knowledge-base operations; "
                "install with `pip install -e .[knowledge-base]`."
            ) from exc
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.db_path))
        return self

    def initialize(self) -> None:
        self._require_connection()
        table_names = self._table_names()
        for name, schema in self._schemas().items():
            if name not in table_names:
                self._db.create_table(name, schema=schema)
                table_names.add(name)

    def table(self, name: str):
        self._require_connection()
        self.initialize()
        if name not in (CHUNKS_TABLE, TRIPLES_TABLE):
            raise ValueError(f"Unknown knowledge-base table: {name}")
        if name not in self._tables:
            self._tables[name] = self._db.open_table(name)
        return self._tables[name]

    def upsert_chunks(self, records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
        prepared = [self._prepare_chunk(record) for record in records]
        if not prepared:
            return {"added": 0, "skipped": 0}
        table = self.table(CHUNKS_TABLE)
        existing = self._existing_keys(table, ("content_hash", "embedding_model"))
        new_rows = []
        for row in prepared:
            key = (row["content_hash"], row["embedding_model"])
            if key in existing:
                continue
            existing.add(key)
            new_rows.append(row)
        if new_rows:
            table.add(new_rows)
        return {"added": len(new_rows), "skipped": len(prepared) - len(new_rows)}

    def upsert_triples(self, records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
        prepared = [self._prepare_triple(record) for record in records]
        if not prepared:
            return {"added": 0, "skipped": 0}
        table = self.table(TRIPLES_TABLE)
        existing = self._existing_keys(table, ("head_entity", "relation", "tail_entity", "chunk_id"))
        new_rows = []
        for row in prepared:
            key = (row["head_entity"], row["relation"], row["tail_entity"], row["chunk_id"])
            if key in existing:
                continue
            existing.add(key)
            new_rows.append(row)
        if new_rows:
            table.add(new_rows)
        return {"added": len(new_rows), "skipped": len(prepared) - len(new_rows)}

    def search_chunks(
        self,
        query_vector: Sequence[float],
        *,
        limit: int = 10,
        source_type: str | None = None,
        document_id: str | None = None,
        source_url_canonical: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self.table(CHUNKS_TABLE).search(list(query_vector))
        filters = []
        if source_type:
            filters.append(f"source_type = {self._literal(source_type)}")
        if document_id:
            filters.append(f"document_id = {self._literal(document_id)}")
        if source_url_canonical:
            filters.append(f"source_url_canonical = {self._literal(source_url_canonical)}")
        if filters:
            query = query.where(" AND ".join(filters))
        return query.limit(limit).to_list()

    def search_triples(
        self,
        query_vector: Sequence[float] | None = None,
        *,
        limit: int = 10,
        head_entity: str | None = None,
        relation: str | None = None,
        tail_entity: str | None = None,
        review_status: str | None = None,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        table = self.table(TRIPLES_TABLE)
        query = table.search(list(query_vector)) if query_vector is not None else table.search()
        filters = []
        for field, value in (
            ("head_entity", head_entity),
            ("relation", relation),
            ("tail_entity", tail_entity),
            ("review_status", review_status),
            ("source_type", source_type),
        ):
            if value is not None:
                filters.append(f"{field} = {self._literal(value)}")
        if filters:
            query = query.where(" AND ".join(filters))
        return query.limit(limit).to_list()

    def update_triple_review_status(
        self,
        triple_id: str,
        review_status: str,
        *,
        confidence: float | None = None,
    ) -> None:
        if review_status not in {"pending", "approved", "rejected"}:
            raise ValueError("review_status must be pending, approved, or rejected")
        values: dict[str, Any] = {
            "review_status": review_status,
            "updated_at": now_iso(),
        }
        if confidence is not None:
            values["confidence"] = float(confidence)
        self.table(TRIPLES_TABLE).update(
            where=f"triple_id = {self._literal(triple_id)}",
            values=values,
        )

    def embed(self, text: str) -> list[float]:
        return self.embedding_provider.embed([text])[0]

    def count(self, table_name: str) -> int:
        return int(self.table(table_name).count_rows())

    def _prepare_chunk(self, record: Mapping[str, Any]) -> dict[str, Any]:
        content = str(record.get("content") or record.get("text") or "").strip()
        if not content:
            raise ValueError("chunk content cannot be empty")
        model = str(record.get("embedding_model") or self.embedding_provider.model_name)
        vector = record.get("embedding") or self.embedding_provider.embed([content])[0]
        chunk_id = str(record.get("chunk_id") or stable_id("chunk", content))
        document_id = str(record.get("document_id") or stable_id("doc", str(record.get("source") or content)))
        timestamp = str(record.get("updated_at") or now_iso())
        source = str(record.get("url") or record.get("source") or "")
        canonical = str(record.get("source_url_canonical") or "")
        return {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": content,
            "embedding": [float(value) for value in vector],
            "url": source,
            "source_url_canonical": canonical,
            "title": str(record.get("title") or ""),
            "source_type": self._source_type(source, record.get("source_type")),
            "source_file": str(record.get("source_file") or source),
            "chunk_index": int(record.get("chunk_index") or 0),
            "content_hash": str(record.get("content_hash") or content_hash(content)),
            "embedding_model": model,
            "created_at": str(record.get("created_at") or timestamp),
            "updated_at": timestamp,
            "metadata_json": self._json(record.get("metadata_json") or record.get("metadata") or {}),
        }

    def _prepare_triple(self, record: Mapping[str, Any]) -> dict[str, Any]:
        head = str(record.get("head_entity") or "").strip()
        relation = str(record.get("relation") or "").strip()
        tail = str(record.get("tail_entity") or "").strip()
        if not head or not relation or not tail:
            raise ValueError("triple requires head_entity, relation, and tail_entity")
        text = str(record.get("triple_text") or f"{head} {relation} {tail}")
        model = str(record.get("embedding_model") or self.embedding_provider.model_name)
        vector = record.get("embedding") or self.embedding_provider.embed([text])[0]
        chunk_id = str(record.get("chunk_id") or "")
        triple_id = str(
            record.get("triple_id")
            or stable_id("triple", "\x1f".join((head, relation, tail, chunk_id)))
        )
        timestamp = str(record.get("updated_at") or now_iso())
        confidence = record.get("confidence")
        return {
            "triple_id": triple_id,
            "head_entity": head,
            "relation": relation,
            "tail_entity": tail,
            "triple_text": text,
            "embedding": [float(value) for value in vector],
            "content": str(record.get("content") or ""),
            "document_id": str(record.get("document_id") or ""),
            "chunk_id": chunk_id,
            "source": str(record.get("source") or ""),
            "title": str(record.get("title") or ""),
            "source_type": self._source_type(record.get("source"), record.get("source_type")),
            "confidence": float(confidence) if confidence is not None else None,
            "review_status": str(record.get("review_status") or "pending"),
            "created_at": str(record.get("created_at") or timestamp),
            "updated_at": timestamp,
            "embedding_model": model,
        }

    def _existing_keys(self, table, fields: tuple[str, ...]) -> set[tuple[Any, ...]]:
        rows = table.to_arrow().to_pylist()
        return {tuple(row.get(field) for field in fields) for row in rows}

    def _schemas(self) -> dict[str, Any]:
        try:
            import pyarrow as pa
        except ImportError as exc:
            raise RuntimeError("pyarrow is required for LanceDB schemas.") from exc
        vector = pa.list_(pa.float32(), self.embedding_provider.dimension)
        return {
            CHUNKS_TABLE: pa.schema(
                [
                    pa.field("chunk_id", pa.string()),
                    pa.field("document_id", pa.string()),
                    pa.field("content", pa.string()),
                    pa.field("embedding", vector),
                    pa.field("url", pa.string()),
                    pa.field("source_url_canonical", pa.string()),
                    pa.field("title", pa.string()),
                    pa.field("source_type", pa.string()),
                    pa.field("source_file", pa.string()),
                    pa.field("chunk_index", pa.int64()),
                    pa.field("content_hash", pa.string()),
                    pa.field("embedding_model", pa.string()),
                    pa.field("created_at", pa.string()),
                    pa.field("updated_at", pa.string()),
                    pa.field("metadata_json", pa.string()),
                ]
            ),
            TRIPLES_TABLE: pa.schema(
                [
                    pa.field("triple_id", pa.string()),
                    pa.field("head_entity", pa.string()),
                    pa.field("relation", pa.string()),
                    pa.field("tail_entity", pa.string()),
                    pa.field("triple_text", pa.string()),
                    pa.field("embedding", vector),
                    pa.field("content", pa.string()),
                    pa.field("document_id", pa.string()),
                    pa.field("chunk_id", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("title", pa.string()),
                    pa.field("source_type", pa.string()),
                    pa.field("confidence", pa.float64()),
                    pa.field("review_status", pa.string()),
                    pa.field("created_at", pa.string()),
                    pa.field("updated_at", pa.string()),
                    pa.field("embedding_model", pa.string()),
                ]
            ),
        }

    def _require_connection(self) -> None:
        if self._db is None:
            self.connect()

    def _table_names(self) -> set[str]:
        if hasattr(self._db, "list_tables"):
            response = self._db.list_tables()
            return {str(name) for name in response.tables}
        return set(self._db.table_names())

    @staticmethod
    def _source_type(source: Any, value: Any) -> str:
        if value:
            return str(value)
        source_text = str(source or "")
        if source_text.startswith(("http://", "https://")):
            return "web"
        suffix = Path(source_text).suffix.lower().lstrip(".")
        return suffix if suffix in {"pdf", "pubmed"} else "local_text"

    @staticmethod
    def _json(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
