from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
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


TEXT_EXTENSIONS = frozenset(
    {
        ".c",
        ".cfg",
        ".csv",
        ".conf",
        ".cpp",
        ".css",
        ".go",
        ".h",
        ".htm",
        ".html",
        ".ini",
        ".json",
        ".java",
        ".js",
        ".log",
        ".md",
        ".py",
        ".rst",
        ".rs",
        ".scss",
        ".sql",
        ".tex",
        ".text",
        ".ts",
        ".tsv",
        ".txt",
        ".vue",
        ".xml",
        ".jsx",
        ".tsx",
        ".toml",
        ".yaml",
        ".yml",
    }
)
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}


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


def load_document_chunks(
    path: str | Path,
    *,
    chunk_size: int = 1800,
    overlap: int = 200,
) -> list[DocumentChunk]:
    """Load a PDF or supported text document and split it into chunks."""
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf_chunks(document_path, chunk_size=chunk_size, overlap=overlap)
    if suffix in TEXT_EXTENSIONS:
        text = extract_text_file(document_path)
        if suffix in {".htm", ".html"}:
            text = _extract_html_text(text)
        return chunk_text(text, chunk_size=chunk_size, overlap=overlap, source=str(document_path))
    raise ValueError(
        f"Unsupported input file format: {document_path}. "
        f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def extract_text_file(path: str | Path) -> str:
    """Read a text-like document using common Unicode and Chinese encodings."""
    document_path = Path(path)
    if not document_path.exists():
        raise FileNotFoundError(document_path)
    if not document_path.is_file():
        raise IsADirectoryError(document_path)

    raw = document_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class _VisibleTextHTMLParser(HTMLParser):
    _ignored_tags = frozenset({"script", "style", "noscript", "template"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self._ignored_tags:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data)


def _extract_html_text(html: str) -> str:
    parser = _VisibleTextHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return html
    return "\n".join(parser.parts)


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
