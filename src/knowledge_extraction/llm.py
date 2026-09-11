from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class StaticLLMClient:
    response: str

    def generate(self, prompt: str) -> str:
        return self.response


@dataclass(frozen=True)
class CommandLLMClient:
    command: tuple[str, ...]
    timeout: int = 1800

    def generate(self, prompt: str) -> str:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            result = subprocess.run(
                list(self.command),
                input=prompt,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LLM command timed out after {self.timeout} seconds. "
                "If this is the first run, the model may still be loading; "
                "rerun with a larger --llm-timeout."
            ) from exc
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            message = stderr or f"LLM command failed with exit code {result.returncode}"
            raise RuntimeError(message)
        return result.stdout


def parse_command(command: str) -> tuple[str, ...]:
    import shlex

    return tuple(shlex.split(command, posix=False))


def missing_python_script(command: tuple[str, ...]) -> Path | None:
    script_args = [Path(part) for part in command[1:] if part.endswith(".py")]
    for script in script_args:
        if not script.exists():
            return script
    return None
