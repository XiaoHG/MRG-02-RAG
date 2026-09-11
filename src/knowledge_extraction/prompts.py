from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = PROJECT_ROOT / "prompts"


def load_prompt_template(name: str, *, prompt_dir: str | Path | None = None) -> str:
    base_dir = Path(prompt_dir) if prompt_dir is not None else PROMPT_DIR
    path = base_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
