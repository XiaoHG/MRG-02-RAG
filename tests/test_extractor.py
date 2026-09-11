from __future__ import annotations

from knowledge_extraction.extractor import build_extraction_prompt, parse_triples_csv, triples_to_csv


def test_build_prompt_contains_schema_and_chunk_text() -> None:
    prompt = build_extraction_prompt("地方性氟中毒可造成氟斑牙。")

    assert "疾病、症状、体征" in prompt
    assert "has_pathological_change" in prompt
    assert "地方性氟中毒可造成氟斑牙。" in prompt


def test_parse_triples_csv_filters_dirty_output_and_invalid_relations() -> None:
    output = """```csv
head_entity,relation,tail_entity
地方性氟中毒,caused_by,过量氟
解释：下面这行不应该进入结果
地方性氟中毒,bad_relation,错误关系
地方性氟中毒,caused_by,过量氟
氟斑牙,has_symptom,牙釉质损害
```
"""

    triples = parse_triples_csv(output, source="doc.pdf", chunk_id="doc-0001")

    assert [(item.head_entity, item.relation, item.tail_entity) for item in triples] == [
        ("地方性氟中毒", "caused_by", "过量氟"),
        ("氟斑牙", "has_symptom", "牙釉质损害"),
    ]
    assert triples[0].source == "doc.pdf"
    assert triples[0].chunk_id == "doc-0001"


def test_triples_to_csv_can_emit_neo4j_columns() -> None:
    triples = parse_triples_csv("Dental fluorosis,has_imaging_feature,enamel opaque white spots")

    csv_text = triples_to_csv(triples)

    assert csv_text.splitlines()[0] == "head_entity,relation,tail_entity"
    assert "Dental fluorosis,has_imaging_feature,enamel opaque white spots" in csv_text
