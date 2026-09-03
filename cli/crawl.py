from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mrg02_rag.catalog import build_sources, default_config, load_config
from mrg02_rag.crawler import crawl_sources
from mrg02_rag.storage import DatasetWriter


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Crawl medical knowledge sources into dataset/")
    parser.add_argument("--config", type=Path, help="JSON file with keywords and URL templates")
    parser.add_argument("--output-dir", type=Path, default=Path("dataset"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config) if args.config else default_config()
    sources = build_sources(config)
    writer = DatasetWriter(args.output_dir)
    results = crawl_sources(sources, writer, fetched_at=datetime.now(timezone.utc))
    print(json.dumps({"records": len(results), "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
