from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json


class DatasetWriter:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def write_group(
        self,
        *,
        group_name: str,
        keyword: str,
        description: str,
        records: list[dict[str, object]],
        fetched_at: datetime,
        source_type: str = "search",
        authority_level: str = "medium",
        access_status: str = "public",
        notes: str = "",
    ) -> Path:
        group_dir = self.base_dir / group_name / fetched_at.strftime("%Y%m%d_%H%M%S")
        group_dir.mkdir(parents=True, exist_ok=True)

        (group_dir / "README.md").write_text(
            f"# {group_name}\n\n{description}\n",
            encoding="utf-8",
        )
        (group_dir / "documents.jsonl").write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )
        manifest = {
            "group_name": group_name,
            "keyword": keyword,
            "description": description,
            "source_type": source_type,
            "authority_level": authority_level,
            "access_status": access_status,
            "notes": notes,
            "fetched_at": fetched_at.isoformat(),
            "record_count": len(records),
            "documents_file": "documents.jsonl",
        }
        (group_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return group_dir
