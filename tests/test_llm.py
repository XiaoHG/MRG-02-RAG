from __future__ import annotations

from dataclasses import dataclass

import pytest

from knowledge_extraction.llm import CommandLLMClient


@dataclass
class _FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str | None = None


def test_command_llm_client_reports_exit_code_when_stderr_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):
        return _FakeResult(returncode=2)

    monkeypatch.setattr("knowledge_extraction.llm.subprocess.run", fake_run)

    client = CommandLLMClient(("python", "runner.py"), timeout=1)

    with pytest.raises(RuntimeError, match="exit code 2"):
        client.generate("prompt")
