from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESULT_DIR = ROOT / "output" / "lancedb_result"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge_base.embeddings import DEFAULT_EMBEDDING_MODEL, create_embedding_provider
from knowledge_base.store import KnowledgeBaseStore


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Query the LanceDB medical knowledge base.")
    parser.add_argument("query", help="Natural-language query or triple text.")
    parser.add_argument("--table", choices=("chunks", "triples"), default="chunks")
    parser.add_argument("--lancedb-dir", type=Path, default=ROOT / "LanceDB")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULT_DIR,
        help=f"Directory for query result JSON files (default: {RESULT_DIR}).",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Local embedding model path (default: {DEFAULT_EMBEDDING_MODEL}).",
    )
    parser.add_argument(
        "--embedding-dimension",
        type=int,
        default=256,
        help="Hash baseline dimension; semantic model dimensions are read from the model.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="Embedding device. auto selects CUDA when available.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source-type")
    parser.add_argument("--document-id")
    parser.add_argument("--head-entity")
    parser.add_argument("--relation")
    parser.add_argument("--tail-entity")
    parser.add_argument("--review-status")
    return parser


def _safe_query_name(query: str, max_length: int = 80) -> str:
    """Create a readable filename fragment without filesystem-sensitive characters."""
    name = re.sub(r"\s+", "_", query.strip())
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"_+", "_", name).strip(" _.")
    return name[:max_length] or "query"


def _new_result_path(output_dir: Path, table: str, query: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
    base_name = f"{table}_{_safe_query_name(query)}_{timestamp}"
    result_path = output_dir / f"{base_name}.json"
    suffix = 1
    while result_path.exists():
        result_path = output_dir / f"{base_name}_{suffix:02d}.json"
        suffix += 1
    return result_path


def _write_query_result(output_dir: Path, table: str, query: str, rows: list[dict]) -> Path:
    result_path = _new_result_path(output_dir, table, query)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table": table,
        "query": query,
        "result_count": len(rows),
        "results": rows,
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return result_path


def main() -> int:
    args = build_parser().parse_args()
    device = None if args.device == "auto" else args.device
    provider = create_embedding_provider(
        args.embedding_model,
        dimension=args.embedding_dimension,
        device=device,
        batch_size=args.batch_size,
    )
    store = KnowledgeBaseStore(args.lancedb_dir, embedding_provider=provider).connect()
    if args.table == "chunks":
        rows = store.search_chunks(
            store.embed(args.query),
            limit=args.limit,
            source_type=args.source_type,
            document_id=args.document_id,
        )
    else:
        rows = store.search_triples(
            store.embed(args.query),
            limit=args.limit,
            head_entity=args.head_entity,
            relation=args.relation,
            tail_entity=args.tail_entity,
            review_status=args.review_status,
            source_type=args.source_type,
        )
    result_path = _write_query_result(args.output_dir, args.table, args.query, rows)
    print(f"Saved {len(rows)} query results to: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
