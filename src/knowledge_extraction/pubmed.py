from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .documents import DocumentChunk, chunk_text


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str
    abstract: str
    journal: str = ""
    year: str = ""

    @property
    def text(self) -> str:
        parts = [self.title, self.abstract]
        return "\n".join(part for part in parts if part)


def fetch_pubmed_articles(query: str, *, max_results: int = 20, timeout: int = 30) -> list[PubMedArticle]:
    ids = _search_pubmed(query, max_results=max_results, timeout=timeout)
    if not ids:
        return []
    xml_text = _fetch_pubmed_xml(ids, timeout=timeout)
    return parse_pubmed_xml(xml_text)


def pubmed_chunks(query: str, *, max_results: int = 20, chunk_size: int = 1800, overlap: int = 200) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for article in fetch_pubmed_articles(query, max_results=max_results):
        source = f"PubMed:{article.pmid}"
        chunks.extend(chunk_text(article.text, chunk_size=chunk_size, overlap=overlap, source=source))
    return chunks


def parse_pubmed_xml(xml_text: str) -> list[PubMedArticle]:
    root = ET.fromstring(xml_text)
    articles: list[PubMedArticle] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//PMID"))
        title = _join_text(article.find(".//ArticleTitle"))
        abstract = " ".join(_join_text(node) for node in article.findall(".//AbstractText")).strip()
        journal = _join_text(article.find(".//Journal/Title"))
        year = _text(article.find(".//PubDate/Year"))
        if pmid and (title or abstract):
            articles.append(PubMedArticle(pmid=pmid, title=title, abstract=abstract, journal=journal, year=year))
    return articles


def _search_pubmed(query: str, *, max_results: int, timeout: int) -> list[str]:
    params = urlencode({"db": "pubmed", "term": query, "retmode": "xml", "retmax": max_results})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    request = Request(url, headers={"User-Agent": "MRG-02-RAG/1.0"})
    with urlopen(request, timeout=timeout) as response:
        root = ET.fromstring(response.read())
    return [_text(node) for node in root.findall(".//Id") if _text(node)]


def _fetch_pubmed_xml(ids: list[str], *, timeout: int) -> str:
    params = urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params}"
    request = Request(url, headers={"User-Agent": "MRG-02-RAG/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _text(node: ET.Element | None) -> str:
    return "" if node is None or node.text is None else node.text.strip()


def _join_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(part.strip() for part in node.itertext() if part.strip())
