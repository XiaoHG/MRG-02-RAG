from __future__ import annotations

import subprocess
import sys

from cli.local_llm_runner import _select_input_device


def test_local_llm_runner_requires_model_path() -> None:
    result = subprocess.run(
        [sys.executable, "cli/local_llm_runner.py"],
        input="prompt",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert "--model-path" in result.stderr


def test_local_llm_runner_rejects_missing_local_model_path() -> None:
    result = subprocess.run(
        [sys.executable, "cli/local_llm_runner.py", "--model-path", "D:/missing/model"],
        input="prompt",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert "Local model path does not exist" in result.stderr


def test_select_input_device_prefers_cuda_map() -> None:
    class FakeDevice(str):
        @property
        def type(self) -> str:
            return self.split(":", 1)[0]

    class FakeTorch:
        class cuda:
            @staticmethod
            def is_available() -> bool:
                return True

        @staticmethod
        def device(value):
            return FakeDevice(str(value))

    model = type("Model", (), {"hf_device_map": {"": 0}, "device": "cpu"})()

    device = _select_input_device(model, FakeTorch)

    assert str(device) == "cuda:0"
