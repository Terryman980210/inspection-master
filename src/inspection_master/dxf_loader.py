from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ezdxf

from .detectors import DetectorRegistry
from .models import InspectionCandidate


@dataclass
class LoadedDrawing:
    path: Path
    document: ezdxf.document.Drawing
    modelspace: ezdxf.layouts.Modelspace
    candidates: list[InspectionCandidate]


def load_drawing(path: str | Path, registry: DetectorRegistry | None = None) -> LoadedDrawing:
    drawing_path = Path(path)
    try:
        document = ezdxf.readfile(drawing_path)
    except (OSError, ezdxf.DXFError) as exc:
        raise ValueError(f"DXFを読み込めませんでした: {exc}") from exc
    modelspace = document.modelspace()
    candidates = (registry or DetectorRegistry()).detect(modelspace)
    return LoadedDrawing(drawing_path, document, modelspace, candidates)

