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

from documents import DocumentChunk, chunk_text, load_pdf_chunks
from llm import CommandLLMClient, StaticLLMClient, missing_python_script, parse_command
from pipeline import extract_triples_from_chunks, prepare_prompt_results, write_extraction_run
from pubmed import pubmed_chunks


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Extract medical knowledge triples from CNKI PDFs and PubMed abstracts.")
    parser.add_argument("--pdf", type=Path, action="append", default=[], help="PDF file to extract.")
    parser.add_argument("--pdf-dir", type=Path, help="Directory containing PDF files.")
    parser.add_argument("--text-file", type=Path, action="append", default=[], help="Plain text file to extract.")
    parser.add_argument("--pubmed-query", help="PubMed query for abstracts.")
    parser.add_argument("--pubmed-max-results", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--run-name", default="v1_extraction")
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
        parser.error("No input chunks were prepared. Provide --pdf, --pdf-dir, --text-file, or --pubmed-query.")
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
    pdf_files = list(args.pdf)
    if args.pdf_dir:
        pdf_files.extend(sorted(args.pdf_dir.glob("*.pdf")))
    for pdf in pdf_files:
        chunks.extend(load_pdf_chunks(pdf, chunk_size=args.chunk_size, overlap=args.overlap))
    for text_file in args.text_file:
        text = text_file.read_text(encoding="utf-8")
        chunks.extend(chunk_text(text, chunk_size=args.chunk_size, overlap=args.overlap, source=str(text_file)))
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


if __name__ == "__main__":
    raise SystemExit(main())
