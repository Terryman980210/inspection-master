from __future__ import annotations

import math
from collections.abc import Callable, Iterable

import ezdxf
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView


BASE_COLOR = QColor("#293241")
HIGHLIGHT_COLOR = QColor("#ffb000")
SELECT_COLOR = QColor("#e63946")


class DrawingView(QGraphicsView):
    source_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#f8fafc"))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._item_map: dict[str, list[QGraphicsItem]] = {}
        self._selected_handle: str | None = None

    def load_entities(self, entities: Iterable[ezdxf.entities.DXFEntity]) -> None:
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self._item_map.clear()
        for entity in entities:
            self._render_entity(entity, entity.dxf.handle)
        bounds = scene.itemsBoundingRect().adjusted(-10, -10, 10, 10)
        scene.setSceneRect(bounds)
        if not bounds.isEmpty():
            self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def highlight(self, handle: str | None) -> None:
        if self._selected_handle:
            for item in self._item_map.get(self._selected_handle, []):
                _set_item_color(item, BASE_COLOR, 0)
        self._selected_handle = handle
        if handle:
            items = self._item_map.get(handle, [])
            for item in items:
                _set_item_color(item, HIGHLIGHT_COLOR, 20)
            if items:
                rect = QRectF()
                for item in items:
                    rect = rect.united(item.sceneBoundingRect())
                padded = rect.adjusted(-20, -20, 20, 20)
                if not padded.isEmpty():
                    self.ensureVisible(padded)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None:
                handle = item.data(0)
                if handle:
                    self.source_selected.emit(str(handle))
                    break
                item = item.parentItem()
        super().mousePressEvent(event)

    def _register(self, item: QGraphicsItem, handle: str) -> None:
        item.setData(0, handle)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.scene().addItem(item)
        self._item_map.setdefault(handle, []).append(item)

    def _render_entity(self, entity: ezdxf.entities.DXFEntity, source_handle: str) -> None:
        kind = entity.dxftype()
        try:
            if kind == "LINE":
                self._path_item(_path_points([entity.dxf.start, entity.dxf.end]), source_handle)
            elif kind == "CIRCLE":
                center, radius = entity.dxf.center, float(entity.dxf.radius)
                path = QPainterPath()
                path.addEllipse(QPointF(center.x, -center.y), radius, radius)
                self._path_item(path, source_handle)
            elif kind == "ARC":
                points = _arc_points(entity.dxf.center, float(entity.dxf.radius), float(entity.dxf.start_angle), float(entity.dxf.end_angle))
                self._path_item(_path_points(points), source_handle)
            elif kind == "LWPOLYLINE":
                points = [(x, y) for x, y, *_ in entity.get_points("xy")]
                if entity.closed and points:
                    points.append(points[0])
                self._path_item(_path_points(points), source_handle)
            elif kind == "POLYLINE":
                points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                if entity.is_closed and points:
                    points.append(points[0])
                self._path_item(_path_points(points), source_handle)
            elif kind in {"TEXT", "MTEXT"}:
                text = entity.dxf.text if kind == "TEXT" else entity.plain_text()
                insert = entity.dxf.insert
                height = float(getattr(entity.dxf, "height", 2.5) or 2.5)
                item = QGraphicsSimpleTextItem(text)
                item.setBrush(BASE_COLOR)
                item.setPos(insert.x, -insert.y)
                item.setScale(max(height / 12, 0.08))
                self._register(item, source_handle)
            elif kind == "DIMENSION":
                for virtual in entity.virtual_entities():
                    self._render_entity(virtual, source_handle)
            elif kind == "INSERT":
                for virtual in entity.virtual_entities():
                    self._render_entity(virtual, source_handle)
        except (AttributeError, TypeError, ValueError, ezdxf.DXFError):
            return

    def _path_item(self, path: QPainterPath, handle: str) -> None:
        item = QGraphicsPathItem(path)
        item.setPen(QPen(BASE_COLOR, 0))
        self._register(item, handle)


def _path_points(points: Iterable) -> QPainterPath:
    materialized = list(points)
    path = QPainterPath()
    if not materialized:
        return path
    first = materialized[0]
    x, y = (first.x, first.y) if hasattr(first, "x") else first[:2]
    path.moveTo(float(x), -float(y))
    for point in materialized[1:]:
        x, y = (point.x, point.y) if hasattr(point, "x") else point[:2]
        path.lineTo(float(x), -float(y))
    return path


def _arc_points(center, radius: float, start: float, end: float) -> list[tuple[float, float]]:
    if end < start:
        end += 360
    steps = max(12, int((end - start) / 5))
    return [
        (center.x + radius * math.cos(math.radians(start + (end - start) * i / steps)),
         center.y + radius * math.sin(math.radians(start + (end - start) * i / steps)))
        for i in range(steps + 1)
    ]


def _set_item_color(item: QGraphicsItem, color: QColor, z: float) -> None:
    item.setZValue(z)
    if isinstance(item, QGraphicsPathItem):
        item.setPen(QPen(color, 0 if z == 0 else 1.5))
    elif isinstance(item, QGraphicsSimpleTextItem):
        item.setBrush(color)
