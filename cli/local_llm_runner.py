from __future__ import annotations

from argparse import ArgumentParser
import os
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prompts import load_prompt_template


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run a local Hugging Face chat model for medical triple extraction.")
    parser.add_argument(
        "--model-path",
        default=os.environ.get("LOCAL_LLM_MODEL"),
        help="Local model directory or Hugging Face model id. Can also be set by LOCAL_LLM_MODEL.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--device-map", default="auto")
    parser.add_argument(
        "--load-in-8bit",
        action="store_true",
        help="Load model with bitsandbytes 8bit quantization. Requires bitsandbytes and accelerate.",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Allow custom model code. Often needed for some local model repositories.",
    )
    parser.add_argument(
        "--system-prompt-file",
        default="system_triples_v1.md",
        help="Prompt filename under prompts/ used as the chat system prompt.",
    )
    return parser


def _prepare_gptq_quantization_config(model_path: str, trust_remote_code: bool, torch_module):
    try:
        from transformers import AutoConfig, GPTQConfig
    except ImportError:
        return None

    try:
        config = AutoConfig.from_pretrained(model_path, trust_remote_code=trust_remote_code)
    except Exception:
        return None

    quantization_config = getattr(config, "quantization_config", None)
    if not isinstance(quantization_config, dict):
        return None

    quant_method = str(quantization_config.get("quant_method", "")).lower()
    if quant_method != "gptq":
        return None

    backend = quantization_config.get("backend") or "auto"
    if torch_module.cuda.is_available():
        major, _minor = torch_module.cuda.get_device_capability()
        if major < 7:
            backend = "gptq_torch"
            _disable_gptq_torch_compile()
            os.environ.setdefault("GPTQ_TORCH_TRITON_DEQUANT", "0")

    quantization_config = dict(quantization_config)
    quantization_config["backend"] = backend
    return GPTQConfig.from_dict(quantization_config)


def _disable_gptq_torch_compile() -> None:
    try:
        from gptqmodel.nn_modules.qlinear.torch import TorchLinear
    except Exception:
        return

    if getattr(TorchLinear.optimize, "_mrg_noop", False):
        return

    def _optimize_noop(self, backend: str | None = None, mode: str | None = None, fullgraph: bool = False):
        self.optimized = True
        return self

    _optimize_noop._mrg_noop = True
    TorchLinear.optimize = _optimize_noop


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    prompt = sys.stdin.read().strip()
    if not prompt:
        parser.error("No prompt received on stdin.")
    if not args.model_path:
        parser.error("Provide --model-path or set LOCAL_LLM_MODEL to your local Qwen/DeepSeek model path.")
    if _looks_like_local_path(args.model_path) and not os.path.exists(args.model_path):
        parser.error(f"Local model path does not exist: {args.model_path}")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        from transformers import BitsAndBytesConfig
    except ImportError:
        parser.error(
            "Missing dependency: transformers. Install LLM dependencies with "
            "`pip install -e .[llm]`, then rerun this command."
        )

    cuda_available = torch.cuda.is_available()
    if cuda_available:
        _log(f"[llm] CUDA available: yes ({torch.cuda.get_device_name(torch.cuda.current_device())})")
    else:
        _log("[llm] CUDA available: no")
    _log(f"[llm] loading tokenizer from {args.model_path}")

    model_kwargs: dict[str, object] = {
        "device_map": args.device_map,
        "trust_remote_code": args.trust_remote_code,
    }
    if args.load_in_8bit:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        model_kwargs["torch_dtype"] = torch.float16 if cuda_available else "auto"

    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=args.trust_remote_code)
    gptq_quantization_config = _prepare_gptq_quantization_config(args.model_path, args.trust_remote_code, torch)
    if gptq_quantization_config is not None:
        model_kwargs["quantization_config"] = gptq_quantization_config
        _log(f"[llm] GPTQ backend set to {gptq_quantization_config.backend}")
    _log(f"[llm] loading model with device_map={args.device_map}")
    model = AutoModelForCausalLM.from_pretrained(args.model_path, **model_kwargs)
    system_prompt = load_prompt_template(args.system_prompt_file).strip()
    input_device = _select_input_device(model, torch)
    _log(f"[llm] selected input device: {input_device}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        text = f"{system_prompt}\n\n{prompt}\n"

    inputs = tokenizer(text, return_tensors="pt")
    inputs = {key: value.to(input_device) for key, value in inputs.items()}

    do_sample = args.temperature > 0
    _log("[llm] generating response")
    output_ids = model.generate(
        **inputs,
        max_new_tokens=args.max_new_tokens,
        do_sample=do_sample,
        temperature=args.temperature if do_sample else None,
        top_p=args.top_p if do_sample else None,
        pad_token_id=tokenizer.eos_token_id,
    )
    generated = output_ids[0][inputs["input_ids"].shape[-1] :]
    text_output = tokenizer.decode(generated, skip_special_tokens=True).strip()
    _log(f"[llm] generation complete, output_chars={len(text_output)}")
    sys.stdout.write(text_output)
    if text_output and not text_output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _select_input_device(model, torch_module):
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        for value in device_map.values():
            device = _normalize_device(value, torch_module)
            if device.type != "cpu":
                return device

    model_device = getattr(model, "device", None)
    if model_device is not None:
        try:
            return torch_module.device(model_device)
        except (TypeError, RuntimeError):
            pass

    if torch_module.cuda.is_available():
        return torch_module.device("cuda:0")
    return torch_module.device("cpu")


def _normalize_device(value, torch_module):
    if isinstance(value, int):
        return torch_module.device(f"cuda:{value}")
    if isinstance(value, str):
        if value.isdigit():
            return torch_module.device(f"cuda:{value}")
        try:
            return torch_module.device(value)
        except (TypeError, RuntimeError):
            return torch_module.device("cpu")
    return torch_module.device("cpu")


def _looks_like_local_path(model_path: str) -> bool:
    return (
        model_path.startswith((".", "/", "\\"))
        or ":\\" in model_path
        or ":/" in model_path
    )


if __name__ == "__main__":
    raise SystemExit(main())

