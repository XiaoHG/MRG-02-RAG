from __future__ import annotations

from datetime import datetime, timezone
import json

from knowledge_extraction.documents import DocumentChunk
from knowledge_extraction.llm import StaticLLMClient
from knowledge_extraction.pipeline import extract_triples_from_chunks, prepare_prompt_results, write_extraction_run


def test_pipeline_extracts_and_writes_review_files(tmp_path) -> None:
    chunks = [
        DocumentChunk(
            chunk_id="cnki-0001",
            text="地方性氟中毒是在高氟环境中摄入过量氟导致。",
            source="references/CNKI/a.pdf",
        )
    ]
    client = StaticLLMClient("head_entity,relation,tail_entity\n地方性氟中毒,caused_by,过量氟\n")

    results = extract_triples_from_chunks(chunks, client)
    run_dir = write_extraction_run(
        results,
        tmp_path,
        run_name="v1_test",
        created_at=datetime(2026, 9, 7, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert results[0].triples[0].tail_entity == "过量氟"
    assert (run_dir / "chunks.jsonl").exists()
    assert (run_dir / "prompts.jsonl").exists()
    assert (run_dir / "raw_outputs.jsonl").exists()
    assert (run_dir / "triples_clean.csv").exists()
    assert (run_dir / "triples_structured.csv").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == 1
    assert manifest["triple_count"] == 1
    assert "source,chunk_id" in (run_dir / "triples_clean.csv").read_text(encoding="utf-8").splitlines()[0]


def test_prepare_prompt_results_does_not_require_llm() -> None:
    chunks = [DocumentChunk(chunk_id="doc-0001", text="Dental fluorosis.", source="doc.txt")]

    results = prepare_prompt_results(chunks)

    assert len(results) == 1
    assert "Dental fluorosis." in results[0].prompt
    assert results[0].raw_output == ""
    assert results[0].triples == []


def test_pipeline_reports_progress() -> None:
    chunks = [DocumentChunk(chunk_id="doc-0001", text="Dental fluorosis.", source="doc.txt")]
    messages: list[str] = []

    extract_triples_from_chunks(chunks, StaticLLMClient("head_entity,relation,tail_entity\nA,caused_by,B\n"), progress_callback=messages.append)

    assert any("extracting doc-0001" in message for message in messages)
    assert any("extracted 1 triples" in message for message in messages)
