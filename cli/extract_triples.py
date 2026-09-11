from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from documents import (
    SUPPORTED_EXTENSIONS,
    DocumentChunk,
    load_document_chunks,
)
from llm import CommandLLMClient, StaticLLMClient, missing_python_script, parse_command
from pipeline import extract_triples_from_chunks, prepare_prompt_results, write_extraction_run
from pubmed import pubmed_chunks


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Extract medical knowledge triples from PDFs and common text documents."
    )
    parser.add_argument("--pdf", type=Path, action="append", default=[], help="PDF file to extract.")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        action="append",
        default=[],
        help="Directory containing PDF files; may be provided multiple times.",
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        action="append",
        default=[],
        help="Text file to extract; may be provided multiple times.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        action="append",
        default=[],
        help="PDF or text-like file to extract; may be provided multiple times.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        default=[],
        help=(
            "Directory to scan recursively for PDF and text-like files; "
            "may be provided multiple times."
        ),
    )
    parser.add_argument("--pubmed-query", help="PubMed query for abstracts.")
    parser.add_argument("--pubmed-max-results", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--run-name", default="extraction")
    parser.add_argument(
        "--llm-command",
        help="Local LLM command that reads prompt from stdin and writes CSV triples to stdout.",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=1800,
        help="Timeout in seconds for each local LLM subprocess call.",
    )
    parser.add_argument("--mock-output", help="Static CSV output used for smoke tests without a local LLM.")
    parser.add_argument(
        "--write-prompts-only",
        action="store_true",
        help="Prepare chunks and prompts without calling a local LLM.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    _log("Preparing input chunks...")
    chunks = _collect_chunks(args)
    if not chunks:
        parser.error(
            "No input chunks were prepared. Provide --pdf, --pdf-dir, --text-file, "
            "--input-file, --input-dir, or --pubmed-query."
        )
    _log(f"Prepared {len(chunks)} chunks.")

    if args.write_prompts_only:
        _log("Writing prompts only; skipping LLM invocation.")
        results = prepare_prompt_results(chunks)
        run_dir = write_extraction_run(results, args.output_dir, run_name=args.run_name, created_at=datetime.now(timezone.utc))
        _log(f"Finished. Output written to {run_dir}.")
        print(json.dumps({"run_dir": str(run_dir), "chunks": len(chunks), "triples": 0, "mode": "write_prompts_only"}, ensure_ascii=False))
        return 0

    if args.mock_output is not None:
        _log("Using mock LLM output.")
        client = StaticLLMClient(args.mock_output)
    elif args.llm_command:
        command = parse_command(args.llm_command)
        _validate_llm_command(command, parser)
        _log(f"Using local LLM command with timeout={args.llm_timeout}s.")
        client = CommandLLMClient(command, timeout=args.llm_timeout)
    else:
        parser.error("Provide --llm-command for a local model runner, or --mock-output for a dry run.")

    results = extract_triples_from_chunks(chunks, client, progress_callback=_log)
    run_dir = write_extraction_run(results, args.output_dir, run_name=args.run_name, created_at=datetime.now(timezone.utc))
    triple_count = sum(len(result.triples) for result in results)
    _log(f"Finished. Wrote {triple_count} triples to {run_dir}.")
    print(json.dumps({"run_dir": str(run_dir), "chunks": len(chunks), "triples": triple_count}, ensure_ascii=False))
    return 0


def _validate_llm_command(command: tuple[str, ...], parser: ArgumentParser) -> None:
    if not command:
        parser.error("--llm-command cannot be empty.")
    missing = missing_python_script(command)
    if missing:
        parser.error(
            "--llm-command points to a missing Python script: "
            f"{missing}. Replace the README placeholder with your real local model runner, "
            "or use --write-prompts-only to generate prompts first."
        )


def _collect_chunks(args) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    input_files = _collect_input_files(args)
    for input_file in input_files:
        chunks.extend(
            load_document_chunks(
                input_file,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
        )
    if args.pubmed_query:
        chunks.extend(
            pubmed_chunks(
                args.pubmed_query,
                max_results=args.pubmed_max_results,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
        )
    return chunks


def _collect_input_files(args) -> list[Path]:
    """Collect explicit files and recursively discovered files without duplicates."""
    candidates: list[Path] = []
    candidates.extend(args.pdf)
    candidates.extend(args.text_file)
    candidates.extend(args.input_file)

    for directory in [*args.pdf_dir, *args.input_dir]:
        if not directory.exists():
            raise FileNotFoundError(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    unique_files: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(resolved)
        if not resolved.is_file():
            raise IsADirectoryError(resolved)
        suffix = resolved.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported input file format: {resolved}. "
                f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            unique_files.append(resolved)
    return sorted(unique_files, key=lambda path: str(path).casefold())


if __name__ == "__main__":
    raise SystemExit(main())
