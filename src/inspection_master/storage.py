from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import InspectionCandidate, normalize_orders


def save_json(path: str | Path, drawing_path: str, candidates: list[InspectionCandidate]) -> None:
    normalize_orders(candidates)
    payload = {
        "schema_version": 1,
        "drawing_path": drawing_path,
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: str | Path) -> tuple[str, list[InspectionCandidate]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("未対応のマスタ形式です")
    return payload.get("drawing_path", ""), [InspectionCandidate.from_dict(item) for item in payload["candidates"]]


def save_csv(path: str | Path, candidates: list[InspectionCandidate]) -> None:
    normalize_orders(candidates)
    fields = ["order", "id", "accepted", "display_text", "category", "value", "instrument", "notes", "source_type", "source_handle", "layer", "confidence"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            if not candidate.accepted:
                continue
            data = candidate.to_dict()
            writer.writerow({field: data.get(field, "") for field in fields})

