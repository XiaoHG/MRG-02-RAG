from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import subprocess
import warnings


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source: str
    page: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def chunk_text(text: str, *, chunk_size: int = 1800, overlap: int = 200, source: str = "text") -> list[DocumentChunk]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to 0 and smaller than chunk_size")

    chunks: list[DocumentChunk] = []
    start = 0
    index = 1
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(
            DocumentChunk(
                chunk_id=f"{Path(source).stem or 'text'}-{index:04d}",
                text=normalized[start:end],
                source=source,
            )
        )
        if end == len(normalized):
            break
        start = end - overlap
        index += 1
    return chunks


def extract_pdf_text(path: str | Path) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    text = _extract_with_pypdf(pdf_path)
    if _looks_readable(text):
        return text

    text = _extract_with_pymupdf(pdf_path)
    if _looks_readable(text):
        return text

    text = _extract_with_pdftotext(pdf_path)
    if _looks_readable(text):
        return text

    return text


def load_pdf_chunks(path: str | Path, *, chunk_size: int = 1800, overlap: int = 200) -> list[DocumentChunk]:
    pdf_path = Path(path)
    text = extract_pdf_text(pdf_path)
    return chunk_text(text, chunk_size=chunk_size, overlap=overlap, source=str(pdf_path))


def _extract_with_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            logging.getLogger("pypdf").setLevel(logging.ERROR)
            reader = PdfReader(str(path))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _extract_with_pymupdf(path: Path) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    try:
        with fitz.open(str(path)) as document:
            return "\n\n".join(page.get_text("text") for page in document)
    except Exception:
        return ""


def _extract_with_pdftotext(path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def _looks_readable(text: str) -> bool:
    if not text.strip():
        return False
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    return replacement_ratio < 0.02
