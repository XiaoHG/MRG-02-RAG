from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Callable

from documents import DocumentChunk
from extractor import Triple, build_extraction_prompt, parse_triples_csv, triples_to_csv
from llm import LLMClient


@dataclass(frozen=True)
class ExtractionResult:
    chunk: DocumentChunk
    prompt: str
    raw_output: str
    triples: list[Triple]


def extract_triples_from_chunks(
    chunks: list[DocumentChunk],
    client: LLMClient,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> list[ExtractionResult]:
    results: list[ExtractionResult] = []
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        if progress_callback:
            progress_callback(f"[{index}/{total}] extracting {chunk.chunk_id} from {chunk.source}")
        prompt = build_extraction_prompt(chunk.text)
        raw_output = client.generate(prompt)
        triples = parse_triples_csv(raw_output, source=chunk.source, chunk_id=chunk.chunk_id)
        results.append(ExtractionResult(chunk=chunk, prompt=prompt, raw_output=raw_output, triples=triples))
        if progress_callback:
            progress_callback(f"[{index}/{total}] extracted {len(triples)} triples from {chunk.chunk_id}")
    return results


def prepare_prompt_results(chunks: list[DocumentChunk]) -> list[ExtractionResult]:
    return [
        ExtractionResult(
            chunk=chunk,
            prompt=build_extraction_prompt(chunk.text),
            raw_output="",
            triples=[],
        )
        for chunk in chunks
    ]


def write_extraction_run(
    results: list[ExtractionResult],
    output_dir: str | Path,
    *,
    run_name: str = "v1_extraction",
    created_at: datetime | None = None,
) -> Path:
    created_at = created_at or datetime.now(timezone.utc)
    run_dir = Path(output_dir) / run_name / created_at.strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    chunks = [result.chunk.to_dict() for result in results]
    (run_dir / "chunks.jsonl").write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )
    (run_dir / "prompts.jsonl").write_text(
        "".join(
            json.dumps({"chunk_id": result.chunk.chunk_id, "prompt": result.prompt}, ensure_ascii=False) + "\n"
            for result in results
        ),
        encoding="utf-8",
    )
    (run_dir / "raw_outputs.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "chunk_id": result.chunk.chunk_id,
                    "source": result.chunk.source,
                    "raw_output": result.raw_output,
                },
                ensure_ascii=False,
            )
            + "\n"
            for result in results
        ),
        encoding="utf-8",
    )

    all_triples = [triple for result in results for triple in result.triples]
    (run_dir / "triples_clean.csv").write_text(triples_to_csv(all_triples, include_source=True), encoding="utf-8")
    (run_dir / "triples_for_neo4j.csv").write_text(triples_to_csv(all_triples), encoding="utf-8")

    manifest = {
        "run_name": run_name,
        "created_at": created_at.isoformat(),
        "chunk_count": len(results),
        "triple_count": len(all_triples),
        "files": {
            "chunks": "chunks.jsonl",
            "prompts": "prompts.jsonl",
            "raw_outputs": "raw_outputs.jsonl",
            "triples_clean": "triples_clean.csv",
            "triples_for_neo4j": "triples_for_neo4j.csv",
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "README.md").write_text(_run_readme(manifest), encoding="utf-8")
    return run_dir


def _run_readme(manifest: dict[str, object]) -> str:
    return (
        f"# {manifest['run_name']}\n\n"
        f"- created_at: {manifest['created_at']}\n"
        f"- chunk_count: {manifest['chunk_count']}\n"
        f"- triple_count: {manifest['triple_count']}\n\n"
        "## Files\n\n"
        "- `chunks.jsonl`: source text chunks prepared for extraction.\n"
        "- `prompts.jsonl`: final prompts sent to the LLM.\n"
        "- `raw_outputs.jsonl`: raw LLM CSV outputs for audit.\n"
        "- `triples_clean.csv`: cleaned triples with source and chunk_id for manual review.\n"
        "- `triples_for_neo4j.csv`: three-column CSV for Neo4j import.\n"
    )


def result_to_dict(result: ExtractionResult) -> dict[str, object]:
    return {
        "chunk": result.chunk.to_dict(),
        "prompt": result.prompt,
        "raw_output": result.raw_output,
        "triples": [asdict(triple) for triple in result.triples],
    }
