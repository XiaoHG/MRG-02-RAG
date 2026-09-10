from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from io import StringIO
import re

from prompts import load_prompt_template
from schema import ALLOWED_ENTITY_TYPES, ALLOWED_RELATION_SET, ALLOWED_RELATIONS


@dataclass(frozen=True)
class Triple:
    head_entity: str
    relation: str
    tail_entity: str
    source: str = ""
    chunk_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def build_extraction_prompt(chunk_text: str) -> str:
    template = load_prompt_template("extraction_triples_v1.md")
    return template.format(
        entity_types="、".join(ALLOWED_ENTITY_TYPES),
        relations=", ".join(ALLOWED_RELATIONS),
        chunk_text=chunk_text.strip(),
    )


def parse_triples_csv(output: str, *, source: str = "", chunk_id: str = "") -> list[Triple]:
    rows = _read_csv_rows(_strip_markdown_fence(output))
    triples: list[Triple] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        if len(row) != 3:
            continue
        head, relation, tail = (_clean_cell(cell) for cell in row)
        if not head or not relation or not tail:
            continue
        if head.lower() in {"head_entity", "头实体"}:
            continue
        if relation not in ALLOWED_RELATION_SET:
            continue
        key = (head, relation, tail)
        if key in seen:
            continue
        seen.add(key)
        triples.append(Triple(head, relation, tail, source=source, chunk_id=chunk_id))
    return triples


def triples_to_csv(triples: list[Triple], *, include_source: bool = False) -> str:
    output = StringIO()
    fieldnames = ["head_entity", "relation", "tail_entity"]
    if include_source:
        fieldnames.extend(["source", "chunk_id"])
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for triple in triples:
        row = triple.to_dict()
        if not include_source:
            row = {key: row[key] for key in fieldnames}
        writer.writerow(row)
    return output.getvalue()


def _read_csv_rows(text: str) -> list[list[str]]:
    clean_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not _is_explanation_line(line)
    ]
    if not clean_lines:
        return []
    try:
        return list(csv.reader(clean_lines))
    except csv.Error:
        return []


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _clean_cell(value: str) -> str:
    value = value.strip().strip("\ufeff")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n\"'")


def _is_explanation_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("以下", "解释", "说明", "注：", "注意", "#", "|"))
