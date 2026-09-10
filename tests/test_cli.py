from __future__ import annotations

from cli.extract_triples import build_parser
from llm import missing_python_script


def test_missing_python_script_detects_placeholder_runner() -> None:
    missing = missing_python_script(("python", "path/to/local_llm_runner.py"))

    assert str(missing) == "path\\to\\local_llm_runner.py" or str(missing) == "path/to/local_llm_runner.py"


def test_extract_triples_parser_exposes_llm_timeout() -> None:
    args = build_parser().parse_args(["--llm-timeout", "3600", "--mock-output", "head_entity,relation,tail_entity"])

    assert args.llm_timeout == 3600
