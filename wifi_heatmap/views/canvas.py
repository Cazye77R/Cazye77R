from __future__ import annotations

import enum
import uuid
from typing import Optional, Union

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSlider,
    QSpinBox,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from models.floor import Floor
from utils.snap import SnapType, snap_point


class CanvasMode(enum.Enum):
    SELECT  = "select"
    RECT    = "rect"
    LINE    = "line"
    ROUTER  = "router"
    MEASURE = "measure"
    DELETE  = "delete"


_ZOOM_MIN:  float = 0.10
_ZOOM_MAX:  float = 5.00
_ZOOM_STEP: float = 1.15

# Z-layer ordering — background < grid < elements < preview < snap < measurements
_Z_BACKGROUND:    int = 0
_Z_GRID:          int = 1
_Z_ELEMENTS:      int = 10
_Z_PREVIEW:       int = 20
_Z_SNAP_INDICATOR: int = 30
_Z_MEASUREMENTS:  int = 100

_ElementItem = Union["_RectElement", "_LineElement"]

# Modes where snap indicator is shown on hover
_DRAW_MODES = {CanvasMode.RECT, CanvasMode.LINE}


# ──────────────────────────────────────────────────────────────────────────────
# Persistent scene items
# ──────────────────────────────────────────────────────────────────────────────

class _GridItem(QGraphicsItem):
    """Infinite cosmetic grid — always 1 px wide regardless of zoom."""

    def __init__(self, grid_size: int = 20) -> None:
        super().__init__()
        self._grid_size = grid_size
        self._pen = QPen(QColor(55, 55, 75), 0)
        self.setZValue(_Z_GRID)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def set_grid_size(self, size: int) -> None:
        self._grid_size = size
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-100_000.0, -100_000.0, 200_000.0, 200_000.0)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        rect = option.exposedRect
        gs   = float(self._grid_size)
        painter.setPen(self._pen)
        left = int(rect.left()  / gs) * gs
        top  = int(rect.top()   / gs) * gs
        x = left
        while x <= rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += gs
        y = top
        while y <= rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += gs


class _SnapIndicator(QGraphicsItem):
    """
    Small icon rendered at the current snap target during drawing.

    Uses ItemIgnoresTransformations so the indicator is always the same
    screen size regardless of zoom level.  Its position is set in scene
    coordinates; rendering is in device (screen) pixels.

    Appearance by snap type
    -----------------------
    "point"  — cyan filled circle + crosshair  (specific point locked)
    "edge"   — green filled circle             (sliding along an edge)
    "grid"   — yellow small dot                (nearest grid crossing)
    """

    _TYPE_COLORS: dict[str, QColor] = {
        "point": QColor("#4fc3f7"),
        "edge":  QColor(100, 220, 120),
        "grid":  QColor(220, 200, 60),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setZValue(_Z_SNAP_INDICATOR)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setVisible(False)
        self._snap_type: SnapType = None

    def update_snap(self, scene_pos: QPointF, snap_type: SnapType) -> None:
        if snap_type is None:
            self.setVisible(False)
            return
        self._snap_type = snap_type
        self.setPos(scene_pos)
        self.setVisible(True)
        self.update()

    def boundingRect(self) -> QRectF:
        # Screen-pixel bounding rect (ItemIgnoresTransformations)
        return QRectF(-9.0, -9.0, 18.0, 18.0)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        color = self._TYPE_COLORS.get(self._snap_type or "", QColor("#4fc3f7"))
        fill  = QColor(color)
        fill.setAlpha(160)

        if self._snap_type == "point":
            # Filled circle (r=4) + crosshair lines (±7 px)
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QRectF(-4.0, -4.0, 8.0, 8.0))
            painter.setPen(QPen(color, 1.0))
            painter.drawLine(QPointF(-8.0,  0.0), QPointF(8.0, 0.0))
            painter.drawLine(QPointF( 0.0, -8.0), QPointF(0.0, 8.0))

        elif self._snap_type == "edge":
            # Hollow circle (r=5) — shows the cursor can slide along the edge
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QRectF(-5.0, -5.0, 10.0, 10.0))

        else:  # "grid"
            # Small filled square
            painter.setPen(QPen(color, 1.0))
            painter.setBrush(QBrush(fill))
            painter.drawRect(QRectF(-3.0, -3.0, 6.0, 6.0))


# ──────────────────────────────────────────────────────────────────────────────
# Element items
# ──────────────────────────────────────────────────────────────────────────────

class _RectElement(QGraphicsRectItem):
    """Drawn rectangle — white 2 px outline, semi-transparent fill."""

    def __init__(self, rect: QRectF, elem_id: str) -> None:
        super().__init__(rect)
        self._elem_id = elem_id
        self.setZValue(_Z_ELEMENTS)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)

    @property
    def elem_id(self) -> str:
        return self._elem_id

    def enable_interaction(self, on: bool) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, on)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    on)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        r = self.rect()
        if self.isSelected():
            painter.setPen(QPen(QColor("#4fc3f7"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(79, 195, 247, 30)))
            painter.drawRect(r)
            hdl = QPen(QColor("#4fc3f7"), 6, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
            painter.setPen(hdl)
            for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                painter.drawPoint(pt)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 25)))
            painter.drawRect(r)


class _LineElement(QGraphicsLineItem):
    """Drawn line — white 3 px; 12 px hit area via custom shape()."""

    def __init__(self, dx: float, dy: float, elem_id: str) -> None:
        super().__init__(0.0, 0.0, dx, dy)
        self._elem_id = elem_id
        self._dx = dx
        self._dy = dy
        self.setZValue(_Z_ELEMENTS)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)

    @property
    def elem_id(self) -> str:
        return self._elem_id

    @property
    def dx(self) -> float:
        return self._dx

    @property
    def dy(self) -> float:
        return self._dy

    def enable_interaction(self, on: bool) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, on)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    on)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(0.0, 0.0)
        path.lineTo(self._dx, self._dy)
        stroker = QPainterPathStroker()
        stroker.setWidth(12.0)
        return stroker.createStroke(path)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self.isSelected():
            painter.setPen(QPen(QColor("#4fc3f7"), 2, Qt.PenStyle.DashLine))
            painter.drawLine(QLineF(0.0, 0.0, self._dx, self._dy))
            dot = QPen(QColor("#4fc3f7"), 8, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
            painter.setPen(dot)
            painter.drawPoint(QPointF(0.0, 0.0))
            painter.drawPoint(QPointF(self._dx, self._dy))
        else:
            painter.setPen(QPen(QColor(255, 255, 255), 3))
            painter.drawLine(QLineF(0.0, 0.0, self._dx, self._dy))


# ──────────────────────────────────────────────────────────────────────────────
# Scale dialog
# ──────────────────────────────────────────────────────────────────────────────

class _ImageScaleDialog(QDialog):
    def __init__(self, current_scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bild skalieren")
        self.setMinimumWidth(340)
        self._scale = max(0.10, min(5.0, current_scale))

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Skalierung:"))
        row.addStretch()
        self._pct_label = QLabel()
        self._pct_label.setMinimumWidth(55)
        row.addWidget(self._pct_label)
        layout.addLayout(row)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(10, 500)
        self._slider.setValue(int(self._scale * 100))
        layout.addWidget(self._slider)

        self._spin = QSpinBox()
        self._spin.setRange(10, 500)
        self._spin.setSuffix(" %")
        self._spin.setValue(int(self._scale * 100))
        layout.addWidget(self._spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)
        self._refresh(int(self._scale * 100))

    def _refresh(self, v: int) -> None:
        self._pct_label.setText(f"{v} %")

    def _on_slider(self, v: int) -> None:
        self._scale = v / 100.0
        self._refresh(v)
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)

    def _on_spin(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)
        self._scale = v / 100.0
        self._refresh(v)

    @property
    def scale(self) -> float:
        return self._scale


# ──────────────────────────────────────────────────────────────────────────────
# Main canvas widget
# ──────────────────────────────────────────────────────────────────────────────

class CanvasWidget(QGraphicsView):
    """
    QGraphicsView-based drawing canvas.

    Z-layers (bottom → top)
    ────────────────────────
    0   background image
    1   grid overlay
    10  drawing elements (rect / line)
    20  draw-in-progress preview
    30  snap indicator          ← _SnapIndicator (ItemIgnoresTransformations)
    100 wifi measurements
    """

    zoom_changed = Signal(float)   # current zoom as % (10.0 – 500.0)

    _MENU_STYLE = (
        "QMenu { background-color:#2a2a3a; color:#e0e0e0; border:1px solid #3a3a4a; }"
        "QMenu::item { padding:4px 20px 4px 10px; }"
        "QMenu::item:selected { background-color:#4fc3f7; color:#1e1e2e; }"
        "QMenu::separator { height:1px; background:#3a3a4a; margin:4px 0; }"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ── Scene ──────────────────────────────────────────────
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-5_000.0, -5_000.0, 10_000.0, 10_000.0)
        self._scene.setBackgroundBrush(QBrush(QColor("#1e1e2e")))
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self._scene)

        # Persistent items (survive floor switches)
        self._grid_item = _GridItem()
        self._grid_item.setVisible(False)
        self._scene.addItem(self._grid_item)

        self._snap_indicator = _SnapIndicator()
        self._scene.addItem(self._snap_indicator)

        self._scene.selectionChanged.connect(self._on_selection_changed)

        # ── View settings ──────────────────────────────────────
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("QGraphicsView { background-color:#1e1e2e; border:none; }")

        # ── Zoom / pan ─────────────────────────────────────────
        self._zoom_factor:   float  = 1.0
        self._pan_active:    bool   = False
        self._pan_origin:    QPointF = QPointF()
        self._space_pressed: bool   = False

        # ── Tool mode ──────────────────────────────────────────
        self._mode: CanvasMode = CanvasMode.SELECT

        # ── Floor management ───────────────────────────────────
        self._floor:  Optional[Floor] = None
        self._floors: dict[int, Floor] = {}

        # ── Background image ───────────────────────────────────
        self._bg_item:      Optional[QGraphicsPixmapItem] = None
        self._bg_move_mode: bool = False

        # ── Drawing ────────────────────────────────────────────
        self._draw_start:   Optional[QPointF]       = None
        self._preview_item: Optional[QGraphicsItem] = None

        # ── Selection ──────────────────────────────────────────
        self._selected_item: Optional[_ElementItem] = None

        # ── Snap settings ──────────────────────────────────────
        self._snap_grid:      bool = False
        self._snap_points:    bool = True
        self._grid_snap_size: int  = 20

        # ── Element registry  elem_id → scene item ─────────────
        self._element_items: dict[str, _ElementItem] = {}

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def set_mode(self, mode: CanvasMode) -> None:
        self._mode = mode
        interactive = (mode == CanvasMode.SELECT)
        for item in self._element_items.values():
            item.enable_interaction(interactive)
        if not interactive:
            self._deselect()
        self._snap_indicator.setVisible(False)
        # Cancel any in-progress drawing when switching modes
        self._cancel_draw()
        self._update_cursor()

    def set_show_grid(self, show: bool) -> None:
        self._grid_item.setVisible(show)

    def set_grid_size(self, size: int) -> None:
        self._grid_snap_size = size
        self._grid_item.set_grid_size(size)

    def set_snap_grid(self, enabled: bool) -> None:
        self._snap_grid = enabled

    def set_snap_points(self, enabled: bool) -> None:
        self._snap_points = enabled

    def load_floor(self, index: int) -> None:
        if index not in self._floors:
            name = "Erdgeschoss" if index == 0 else f"Etage {index}"
            self._floors[index] = Floor(name=name, level=index)
        self._floor = self._floors[index]
        self._rebuild_scene()

    def register_floor(self, index: int, floor: Floor) -> None:
        self._floors[index] = floor
        if self._floor is None or index == 0:
            self.load_floor(index)

    def current_floor(self) -> Optional[Floor]:
        return self._floor

    # ──────────────────────────────────────────────────────────
    # Zoom
    # ──────────────────────────────────────────────────────────

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom_factor * factor))
        actual = new_zoom / self._zoom_factor
        if abs(actual - 1.0) < 1e-9:
            return
        self._zoom_factor = new_zoom
        self.scale(actual, actual)
        self.zoom_changed.emit(self._zoom_factor * 100.0)

    # ──────────────────────────────────────────────────────────
    # Scene rebuild
    # ──────────────────────────────────────────────────────────

    def _rebuild_scene(self) -> None:
        self._cancel_draw()
        self._selected_item = None

        _persistent = {self._grid_item, self._snap_indicator}
        for item in list(self._scene.items()):
            if item not in _persistent:
                self._scene.removeItem(item)

        self._bg_item = None
        self._bg_move_mode = False
        self._element_items.clear()
        self._snap_indicator.setVisible(False)

        if self._floor is None:
            return
        if self._floor.background_image:
            self._load_bg_pixmap(self._floor.background_image)
        self._restore_elements()
        self._update_cursor()

    def _load_bg_pixmap(self, path: str) -> None:
        px = QPixmap(path)
        if px.isNull():
            return
        item = QGraphicsPixmapItem(px)
        item.setZValue(_Z_BACKGROUND)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        if self._floor:
            ox, oy = self._floor.bg_offset
            item.setPos(ox, oy)
            item.setScale(self._floor.bg_scale)
        self._scene.addItem(item)
        self._bg_item = item

    def _restore_elements(self) -> None:
        if self._floor is None:
            return
        in_select = (self._mode == CanvasMode.SELECT)
        for d in self._floor.elements:
            t = d.get("type")
            if t == "rect":
                item: _ElementItem = self._make_rect_item(d)
            elif t == "line":
                item = self._make_line_item(d)
            else:
                continue
            item.enable_interaction(in_select)
            self._scene.addItem(item)
            self._element_items[d["id"]] = item

    def _make_rect_item(self, d: dict) -> _RectElement:
        item = _RectElement(QRectF(0.0, 0.0, d["w"], d["h"]), d["id"])
        item.setPos(d["x"], d["y"])
        return item

    def _make_line_item(self, d: dict) -> _LineElement:
        item = _LineElement(d["x2"] - d["x1"], d["y2"] - d["y1"], d["id"])
        item.setPos(d["x1"], d["y1"])
        return item

    # ──────────────────────────────────────────────────────────
    # Snap
    # ──────────────────────────────────────────────────────────

    def _do_snap(self, raw_scene_pt: QPointF) -> tuple[QPointF, SnapType]:
        """Call utils.snap.snap_point() with current floor elements and settings."""
        elements = self._floor.elements if self._floor else []
        return snap_point(
            raw_scene_pt, elements, self._grid_snap_size,
            self._snap_points, self._snap_grid, self._zoom_factor,
        )

    # ──────────────────────────────────────────────────────────
    # Drawing helpers
    # ──────────────────────────────────────────────────────────

    def _cancel_draw(self) -> None:
        if self._preview_item is not None:
            self._scene.removeItem(self._preview_item)
            self._preview_item = None
        self._draw_start = None

    def _start_rect(self, start: QPointF) -> None:
        self._draw_start = start
        preview = QGraphicsRectItem(start.x(), start.y(), 0.0, 0.0)
        preview.setPen(QPen(QColor(255, 255, 255, 160), 2, Qt.PenStyle.DashLine))
        preview.setBrush(QBrush(QColor(255, 255, 255, 15)))
        preview.setZValue(_Z_PREVIEW)
        self._scene.addItem(preview)
        self._preview_item = preview

    def _start_line(self, start: QPointF) -> None:
        self._draw_start = start
        preview = QGraphicsLineItem(start.x(), start.y(), start.x(), start.y())
        preview.setPen(QPen(QColor(255, 255, 255, 160), 3, Qt.PenStyle.DashLine))
        preview.setZValue(_Z_PREVIEW)
        self._scene.addItem(preview)
        self._preview_item = preview

    def _update_preview(self, end: QPointF) -> None:
        if self._preview_item is None or self._draw_start is None:
            return
        s = self._draw_start
        if isinstance(self._preview_item, QGraphicsRectItem):
            self._preview_item.setRect(
                min(s.x(), end.x()), min(s.y(), end.y()),
                abs(end.x() - s.x()), abs(end.y() - s.y()),
            )
        elif isinstance(self._preview_item, QGraphicsLineItem):
            ln = self._preview_item.line()
            self._preview_item.setLine(ln.x1(), ln.y1(), end.x(), end.y())

    def _finalize_draw(self, end: QPointF) -> None:
        if self._preview_item is not None:
            self._scene.removeItem(self._preview_item)
            self._preview_item = None

        start = self._draw_start
        self._draw_start = None
        self._snap_indicator.setVisible(False)

        if start is None or self._floor is None:
            return

        elem_id = str(uuid.uuid4())

        if self._mode == CanvasMode.RECT:
            w = abs(end.x() - start.x())
            h = abs(end.y() - start.y())
            if w < 3 or h < 3:
                return
            d: dict = {
                "type": "rect",
                "x": min(start.x(), end.x()), "y": min(start.y(), end.y()),
                "w": w, "h": h, "id": elem_id,
            }
            item: _ElementItem = self._make_rect_item(d)

        elif self._mode == CanvasMode.LINE:
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            if abs(dx) < 3 and abs(dy) < 3:
                return
            d = {
                "type": "line",
                "x1": start.x(), "y1": start.y(),
                "x2": end.x(),   "y2": end.y(),
                "id": elem_id,
            }
            item = self._make_line_item(d)

        else:
            return

        item.enable_interaction(self._mode == CanvasMode.SELECT)
        self._floor.elements.append(d)
        self._scene.addItem(item)
        self._element_items[elem_id] = item

    # ──────────────────────────────────────────────────────────
    # Selection & deletion
    # ──────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        sel = [i for i in self._scene.selectedItems()
               if isinstance(i, (_RectElement, _LineElement))]
        self._selected_item = sel[0] if sel else None

    def _deselect(self) -> None:
        self._scene.clearSelection()
        self._selected_item = None

    def _element_item_at(self, vp_pos: QPointF) -> Optional[_ElementItem]:
        for item in self.items(vp_pos.toPoint()):
            if isinstance(item, (_RectElement, _LineElement)):
                return item
        return None

    def _delete_element_item(self, item: _ElementItem) -> None:
        eid = item.elem_id
        if self._floor is not None:
            self._floor.elements = [e for e in self._floor.elements
                                    if e.get("id") != eid]
        self._element_items.pop(eid, None)
        if item is self._selected_item:
            self._selected_item = None
        self._scene.removeItem(item)

    def _sync_item_to_model(self, item: _ElementItem) -> None:
        if self._floor is None:
            return
        eid = item.elem_id
        pos = item.pos()
        for e in self._floor.elements:
            if e.get("id") != eid:
                continue
            if isinstance(item, _RectElement):
                e["x"] = pos.x()
                e["y"] = pos.y()
            elif isinstance(item, _LineElement):
                e["x1"] = pos.x()
                e["y1"] = pos.y()
                e["x2"] = pos.x() + item.dx
                e["y2"] = pos.y() + item.dy
            break

    # ──────────────────────────────────────────────────────────
    # Context menu — background image
    # ──────────────────────────────────────────────────────────

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._MENU_STYLE)
        menu.addAction("Hintergrundbild laden …").triggered.connect(
            self._load_background_image)
        if self._bg_item is not None:
            menu.addSeparator()
            menu.addAction("Bild skalieren …").triggered.connect(self._scale_bg)
            menu.addAction(
                "Bild verschieben beenden" if self._bg_move_mode
                else "Bild verschieben"
            ).triggered.connect(self._toggle_bg_move)
            menu.addSeparator()
            menu.addAction("Hintergrundbild entfernen").triggered.connect(self._remove_bg)
        menu.exec(event.globalPosition().toPoint())

    def _load_background_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Hintergrundbild laden", "",
            "Bilder (*.png *.jpg *.jpeg *.bmp);;Alle Dateien (*)",
        )
        if not path:
            return
        if self._floor is None:
            self.load_floor(0)
        if self._bg_item is not None:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        assert self._floor is not None
        self._floor.background_image = path
        self._floor.bg_offset = (0.0, 0.0)
        self._floor.bg_scale  = 1.0
        self._load_bg_pixmap(path)

    def _scale_bg(self) -> None:
        if self._floor is None or self._bg_item is None:
            return
        dlg = _ImageScaleDialog(self._floor.bg_scale, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._floor.bg_scale = dlg.scale
        self._bg_item.setScale(dlg.scale)

    def _toggle_bg_move(self) -> None:
        self._bg_move_mode = not self._bg_move_mode
        if self._bg_item is not None:
            self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                                  self._bg_move_mode)
            self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                                  self._bg_move_mode)
        self._update_cursor()

    def _remove_bg(self) -> None:
        if self._bg_item is not None:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        if self._floor is not None:
            self._floor.background_image = None
            self._floor.bg_offset = (0.0, 0.0)
            self._floor.bg_scale  = 1.0
        self._bg_move_mode = False
        self._update_cursor()

    # ──────────────────────────────────────────────────────────
    # Event overrides
    # ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            self._apply_zoom(_ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        if k == Qt.Key.Key_Escape and not event.isAutoRepeat():
            self._cancel_draw()
            self._snap_indicator.setVisible(False)
            event.accept()
        elif k == Qt.Key.Key_Delete and not event.isAutoRepeat():
            if self._mode == CanvasMode.SELECT and self._selected_item is not None:
                self._delete_element_item(self._selected_item)
            event.accept()
        elif k == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self._update_cursor()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            if not self._pan_active:
                self._update_cursor()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # ── Pan ────────────────────────────────────────────────
        if (event.button() == Qt.MouseButton.MiddleButton
                or (self._space_pressed
                    and event.button() == Qt.MouseButton.LeftButton)):
            self._pan_active = True
            self._pan_origin = event.position()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        raw_pt            = self.mapToScene(event.position().toPoint())
        snapped, snap_type = self._do_snap(raw_pt)

        if self._mode == CanvasMode.RECT:
            # Keep indicator visible at start point while drawing
            self._snap_indicator.update_snap(snapped, snap_type)
            self._start_rect(snapped)
            event.accept()

        elif self._mode == CanvasMode.LINE:
            self._snap_indicator.update_snap(snapped, snap_type)
            self._start_line(snapped)
            event.accept()

        elif self._mode == CanvasMode.SELECT:
            super().mousePressEvent(event)   # Qt handles selection + item drag

        elif self._mode == CanvasMode.DELETE:
            hit = self._element_item_at(event.position())
            if hit is not None:
                self._delete_element_item(hit)
            event.accept()

        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # ── Pan ────────────────────────────────────────────────
        if self._pan_active:
            delta = event.position() - self._pan_origin
            self._pan_origin = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            event.accept()
            return

        # ── Draw modes — compute snap, update indicator + preview ──
        if self._mode in _DRAW_MODES:
            raw_pt             = self.mapToScene(event.position().toPoint())
            snapped, snap_type = self._do_snap(raw_pt)
            self._snap_indicator.update_snap(snapped, snap_type)
            if self._draw_start is not None:
                self._update_preview(snapped)
            event.accept()
            return

        # ── Other modes ────────────────────────────────────────
        self._snap_indicator.setVisible(False)
        super().mouseMoveEvent(event)

        # Keep bg_offset in sync while dragging the background image
        if (self._bg_move_mode and self._bg_item is not None
                and self._floor is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            p = self._bg_item.pos()
            self._floor.bg_offset = (p.x(), p.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # ── Pan end ────────────────────────────────────────────
        if self._pan_active and event.button() in (
            Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton
        ):
            self._pan_active = False
            self._update_cursor()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._draw_start is not None:
                raw_pt             = self.mapToScene(event.position().toPoint())
                snapped, snap_type = self._do_snap(raw_pt)
                self._finalize_draw(snapped)
                # Restore hover indicator at the cursor position after finalizing
                self._snap_indicator.update_snap(snapped, snap_type)
                event.accept()
                return

        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == CanvasMode.SELECT and self._selected_item is not None:
                self._sync_item_to_model(self._selected_item)
            if (self._bg_move_mode and self._bg_item is not None
                    and self._floor is not None):
                p = self._bg_item.pos()
                self._floor.bg_offset = (p.x(), p.y())

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _update_cursor(self) -> None:
        if self._bg_move_mode:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            return
        if self._space_pressed:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            return
        cursor_map: dict[CanvasMode, Qt.CursorShape] = {
            CanvasMode.SELECT:  Qt.CursorShape.ArrowCursor,
            CanvasMode.RECT:    Qt.CursorShape.CrossCursor,
            CanvasMode.LINE:    Qt.CursorShape.CrossCursor,
            CanvasMode.ROUTER:  Qt.CursorShape.CrossCursor,
            CanvasMode.MEASURE: Qt.CursorShape.CrossCursor,
            CanvasMode.DELETE:  Qt.CursorShape.ForbiddenCursor,
        }
        self.setCursor(QCursor(cursor_map.get(self._mode, Qt.CursorShape.ArrowCursor)))
