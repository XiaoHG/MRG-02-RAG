from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge_base.embeddings import DEFAULT_EMBEDDING_MODEL, create_embedding_provider
from knowledge_base.ingest import ingest_extraction_triples, ingest_trafilatura_documents
from knowledge_base.store import KnowledgeBaseStore


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Build the LanceDB medical knowledge base incrementally.")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "output" / "trafilatura")
    parser.add_argument("--extraction-dir", type=Path, default=ROOT / "output" / "extraction")
    parser.add_argument("--lancedb-dir", type=Path, default=ROOT / "LanceDB")
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
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--chunk-size", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=50)
    return parser


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
    store.initialize()
    chunk_result = ingest_trafilatura_documents(
        store,
        args.input_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    ) if args.input_dir.exists() else {"added": 0, "skipped": 0}
    triple_result = ingest_extraction_triples(store, args.extraction_dir) if args.extraction_dir.exists() else {
        "added": 0,
        "skipped": 0,
    }
    payload = {
        "lancedb_dir": str(args.lancedb_dir),
        "embedding_model": provider.model_name,
        "chunks": chunk_result,
        "triples": triple_result,
        "knowledge_chunks": store.count("knowledge_chunks"),
        "knowledge_triples": store.count("knowledge_triples"),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
