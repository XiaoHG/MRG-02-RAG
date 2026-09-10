from __future__ import annotations

from pathlib import Path

from prompts import load_prompt_template


def test_load_prompt_template_reads_prompt_file(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "sample.md").write_text("hello {name}", encoding="utf-8")

    template = load_prompt_template("sample.md", prompt_dir=prompt_dir)

    assert template.format(name="world") == "hello world"


def test_v1_extraction_prompt_is_external_file() -> None:
    template = load_prompt_template("extraction_triples_v1.md")

    assert "{chunk_text}" in template
    assert "head_entity,relation,tail_entity" in template
