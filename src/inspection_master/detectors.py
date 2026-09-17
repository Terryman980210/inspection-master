from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable

import ezdxf

from .models import InspectionCandidate, normalize_orders


NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("diameter", re.compile(rf"(?i)(?:\d+\s*[-x×]\s*)?[φΦØ⌀]\s*{NUMBER}")),
    ("radius", re.compile(rf"(?i)\bR\s*{NUMBER}")),
    ("chamfer", re.compile(rf"(?i)\bC\s*{NUMBER}")),
    ("thread", re.compile(rf"(?i)\bM\s*{NUMBER}(?:\s*[x×]\s*{NUMBER})?")),
    ("toleranced_dimension", re.compile(rf"{NUMBER}\s*(?:±|\+/-|\+\s*{NUMBER}\s*/\s*-\s*{NUMBER})")),
]


def _plain_text(entity: ezdxf.entities.DXFEntity) -> str:
    if entity.dxftype() == "TEXT":
        return entity.dxf.text.strip()
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return ""


def _insert_xy(entity: ezdxf.entities.DXFEntity) -> tuple[float, float] | None:
    point = getattr(entity.dxf, "insert", None)
    if point is None:
        return None
    return float(point.x), float(point.y)


def _number(text: str) -> float | None:
    match = re.search(NUMBER, text)
    return float(match.group()) if match else None


class CandidateDetector(ABC):
    @abstractmethod
    def detect(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> list[InspectionCandidate]:
        raise NotImplementedError


class DimensionDetector(CandidateDetector):
    def detect(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> list[InspectionCandidate]:
        found: list[InspectionCandidate] = []
        for entity in entities:
            if entity.dxftype() != "DIMENSION":
                continue
            try:
                value = float(entity.get_measurement())
            except (TypeError, ValueError, ezdxf.DXFError):
                value = None
            override = getattr(entity.dxf, "text", "")
            display = override if override and override not in {"<>", " "} else _format_value(value)
            dim_type = int(entity.dxf.dimtype) & 15
            category = {
                0: "linear_dimension",
                1: "linear_dimension",
                2: "angular_dimension",
                3: "diameter",
                4: "radius",
                5: "angular_dimension",
                6: "ordinate_dimension",
            }.get(dim_type, "dimension")
            text_midpoint = getattr(entity.dxf, "text_midpoint", None)
            position = None
            if text_midpoint is not None:
                position = (float(text_midpoint.x), float(text_midpoint.y))
            found.append(
                InspectionCandidate(
                    id="",
                    source_type="DIMENSION",
                    category=category,
                    display_text=display,
                    value=value,
                    position=position,
                    source_handle=entity.dxf.handle,
                    layer=entity.dxf.layer,
                    confidence=1.0,
                )
            )
        return found


class TextDimensionDetector(CandidateDetector):
    def detect(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> list[InspectionCandidate]:
        found: list[InspectionCandidate] = []
        for entity in entities:
            if entity.dxftype() not in {"TEXT", "MTEXT"}:
                continue
            text = _plain_text(entity)
            matches = [
                (match.start(), match.end(), category, match.group(0).strip())
                for category, pattern in PATTERNS
                for match in pattern.finditer(text)
            ]
            accepted_spans: list[tuple[int, int]] = []
            for start, end, category, matched_text in sorted(matches):
                if any(start < used_end and end > used_start for used_start, used_end in accepted_spans):
                    continue
                accepted_spans.append((start, end))
                found.append(
                    InspectionCandidate(
                        id="",
                        source_type=entity.dxftype(),
                        category=category,
                        display_text=matched_text,
                        value=_number(matched_text),
                        position=_insert_xy(entity),
                        source_handle=entity.dxf.handle,
                        layer=entity.dxf.layer,
                        confidence=0.75,
                        metadata={"full_text": text, "text_span": [start, end]},
                    )
                )
        return found


class NumericTextDetector(CandidateDetector):
    """Standalone numbers are review candidates, never confirmed dimensions."""

    def detect(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> list[InspectionCandidate]:
        found = []
        for entity in entities:
            if entity.dxftype() not in {"TEXT", "MTEXT"}:
                continue
            text = _plain_text(entity)
            for match in re.finditer(rf"(?m)^[ \t]*([+-]?{NUMBER})[ \t]*$", text):
                label = match.group(1)
                found.append(InspectionCandidate(
                    id="", source_type=entity.dxftype(),
                    category="数値文字（要確認）", display_text=label,
                    source_handle=entity.dxf.handle, layer=entity.dxf.layer,
                    value=float(label), position=_insert_xy(entity),
                    accepted=False, confidence=0.4,
                    metadata={"full_text": text, "text_span": list(match.span(1)),
                              "detector": "numeric_text",
                              "review_reason": "数字のみの文字。寸法・番号の区別と測定箇所は人が確認。"},
                ))
        return found


class DetectorRegistry:
    def __init__(self, detectors: list[CandidateDetector] | None = None) -> None:
        self.detectors = detectors if detectors is not None else [DimensionDetector(), TextDimensionDetector(), NumericTextDetector()]

    def detect(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> list[InspectionCandidate]:
        materialized = list(entities)
        candidates: list[InspectionCandidate] = []
        for detector in self.detectors:
            candidates.extend(detector.detect(materialized))
        candidates.sort(key=lambda c: (-(c.position or (0, 0))[1], (c.position or (0, 0))[0], c.source_handle))
        for index, candidate in enumerate(candidates, 1):
            candidate.id = f"C{index:04d}"
        normalize_orders(candidates)
        return candidates


def _format_value(value: float | None) -> str:
    if value is None:
        return "(値を取得できません)"
    return f"{value:.6f}".rstrip("0").rstrip(".")
