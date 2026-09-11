from __future__ import annotations

from pathlib import Path

from cli.extract_triples import _collect_input_files, build_parser
from llm import missing_python_script


def test_missing_python_script_detects_placeholder_runner() -> None:
    missing = missing_python_script(("python", "path/to/local_llm_runner.py"))

    assert str(missing) == "path\\to\\local_llm_runner.py" or str(missing) == "path/to/local_llm_runner.py"


def test_extract_triples_parser_exposes_llm_timeout() -> None:
    args = build_parser().parse_args(["--llm-timeout", "3600", "--mock-output", "head_entity,relation,tail_entity"])

    assert args.llm_timeout == 3600


def test_extract_triples_parser_accepts_multiple_input_directories() -> None:
    args = build_parser().parse_args(
        [
            "--input-dir",
            "references",
            "--input-dir",
            "tests",
            "--input-file",
            "README.md",
            "--mock-output",
            "head_entity,relation,tail_entity",
        ]
    )

    assert len(args.input_dir) == 2
    assert args.input_file == [Path("README.md")]


def test_collect_input_files_recurses_and_deduplicates(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    (first / "nested").mkdir(parents=True)
    second.mkdir()
    shared = first / "nested" / "shared.md"
    shared.write_text("shared", encoding="utf-8")
    (first / "nested" / "page.html").write_text("<p>html</p>", encoding="utf-8")
    (second / "data.json").write_text('{"key": "value"}', encoding="utf-8")
    (second / "image.png").write_bytes(b"not a text input")

    args = build_parser().parse_args(
        [
            "--input-dir",
            str(first),
            "--input-dir",
            str(second),
            "--input-file",
            str(shared),
        ]
    )

    files = _collect_input_files(args)

    assert files == sorted(
        [shared.resolve(), (first / "nested" / "page.html").resolve(), (second / "data.json").resolve()],
        key=lambda path: str(path).casefold(),
    )
