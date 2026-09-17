from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InspectionCandidate:
    id: str
    source_type: str
    category: str
    display_text: str
    source_handle: str
    layer: str = "0"
    value: float | None = None
    tolerance_upper: float | None = None
    tolerance_lower: float | None = None
    position: tuple[float, float] | None = None
    accepted: bool = True
    order: int | None = None
    instrument: str = ""
    notes: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.position is not None:
            data["position"] = list(self.position)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InspectionCandidate":
        values = dict(data)
        if values.get("position") is not None:
            values["position"] = tuple(values["position"])
        return cls(**values)



def normalize_orders(candidates: list[InspectionCandidate]) -> None:
    """List order is authoritative; only accepted items receive a sequence number."""
    order = 0
    for candidate in candidates:
        if candidate.accepted:
            order += 1
            candidate.order = order
        else:
            candidate.order = None
