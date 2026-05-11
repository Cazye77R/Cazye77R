from __future__ import annotations

import enum
import math
import uuid
from typing import Optional, Union

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
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
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsObject,
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
from models.measurement import Measurement
from utils.colors import create_legend_gradient, dbm_to_color
from utils.snap import SnapType, snap_point
from views.commands import (
    AddElementCommand,
    AddMeasurementCommand,
    MoveElementCommand,
    RemoveElementCommand,
    RemoveMeasurementCommand,
    SetBackgroundCommand,
    SetRouterCommand,
)

try:
    from views.heatmap_overlay import HeatmapOverlay as _HeatmapOverlay
except ImportError:
    _HeatmapOverlay = None  # type: ignore[assignment,misc]


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

# Z-layer ordering
_Z_BACKGROUND:     int = 0
_Z_GRID:           int = 1
_Z_ELEMENTS:       int = 10
_Z_PREVIEW:        int = 20
_Z_SNAP_INDICATOR: int = 30
_Z_HEATMAP:        int = 5
_Z_ROUTER_LINE:    int = 49
_Z_ROUTER:         int = 50
_Z_MEASUREMENTS:   int = 100
_Z_PENDING:        int = 110

_ElementItem = Union["_RectElement", "_LineElement"]
_DRAW_MODES  = {CanvasMode.RECT, CanvasMode.LINE}


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
    """Snap target indicator — constant screen size via ItemIgnoresTransformations."""

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
        return QRectF(-9.0, -9.0, 18.0, 18.0)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        color = self._TYPE_COLORS.get(self._snap_type or "", QColor("#4fc3f7"))
        fill  = QColor(color)
        fill.setAlpha(160)

        if self._snap_type == "point":
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QRectF(-4.0, -4.0, 8.0, 8.0))
            painter.setPen(QPen(color, 1.0))
            painter.drawLine(QPointF(-8.0,  0.0), QPointF(8.0, 0.0))
            painter.drawLine(QPointF( 0.0, -8.0), QPointF(0.0, 8.0))
        elif self._snap_type == "edge":
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QRectF(-5.0, -5.0, 10.0, 10.0))
        else:
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
# Measurement items
# ──────────────────────────────────────────────────────────────────────────────

class _PendingMarker(QGraphicsObject):
    """Pulsing blue circle shown after the user clicks in MEASURE mode.

    Uses ItemIgnoresTransformations so the dot stays the same screen size
    at any zoom level.  Owned QTimer drives the pulse animation.
    """

    def __init__(self) -> None:
        super().__init__()
        self._phase: float = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)   # ~20 fps
        self.setZValue(_Z_PENDING)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.18) % (2 * math.pi)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-12.0, -12.0, 24.0, 24.0)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        alpha = int(70 + 185 * (0.5 + 0.5 * math.sin(self._phase)))
        fill  = QColor(79, 195, 247, alpha)
        painter.setPen(QPen(QColor(79, 195, 247, 230), 2))
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(QRectF(-7.0, -7.0, 14.0, 14.0))
        # Cross-hair tick marks
        painter.setPen(QPen(QColor(79, 195, 247, 180), 1))
        painter.drawLine(QPointF(-11.0, 0.0), QPointF(-8.0,  0.0))
        painter.drawLine(QPointF(  8.0, 0.0), QPointF(11.0,  0.0))
        painter.drawLine(QPointF(  0.0, -11.0), QPointF(0.0, -8.0))
        painter.drawLine(QPointF(  0.0,   8.0), QPointF(0.0, 11.0))


class _MeasurementItem(QGraphicsEllipseItem):
    """Permanent colored measurement dot (14 px diameter in scene coords)."""

    _DIAM = 14.0
    _RAD  = 7.0

    def __init__(
        self, m: Measurement, min_dbm: float, max_dbm: float
    ) -> None:
        super().__init__(-self._RAD, -self._RAD, self._DIAM, self._DIAM)
        self._m     = m
        self._color = dbm_to_color(m.dbm, min_dbm, max_dbm)
        self.setBrush(QBrush(self._color))
        self.setPen(QPen(QColor(0, 0, 0, 200), 2))
        self.setZValue(_Z_MEASUREMENTS)
        self.setPos(m.x, m.y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        ts = m.timestamp.strftime("%H:%M:%S")
        self.setToolTip(
            f"{m.dbm:.1f} dBm  |  {m.ssid}  |  {m.band}  |  {ts}"
        )

    @property
    def measurement(self) -> Measurement:
        return self._m

    def enable_selection(self, on: bool) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, on)

    def update_color(self, min_dbm: float, max_dbm: float) -> None:
        self._color = dbm_to_color(self._m.dbm, min_dbm, max_dbm)
        self.setBrush(QBrush(self._color))

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self.isSelected():
            painter.setPen(QPen(QColor("#4fc3f7"), 2))
            sel_fill = QColor(self._color)
            sel_fill.setAlpha(220)
            painter.setBrush(QBrush(sel_fill))
            # Outer selection ring
            painter.drawEllipse(QRectF(-self._RAD - 3, -self._RAD - 3,
                                       self._DIAM + 6, self._DIAM + 6))
        else:
            painter.setPen(QPen(QColor(0, 0, 0, 200), 2))
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(QRectF(-self._RAD, -self._RAD, self._DIAM, self._DIAM))


# ──────────────────────────────────────────────────────────────────────────────
# Router item
# ──────────────────────────────────────────────────────────────────────────────

class _RouterItem(QGraphicsObject):
    """Router icon: drawn antenna with WiFi arcs and soft pulse glow."""

    moved = Signal(QPointF)   # emitted on every position change during drag

    def __init__(self) -> None:
        super().__init__()
        self._phase: float = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)
        self.setZValue(_Z_ROUTER)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,         False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,      False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setToolTip("Router — Rechtsklick: Optionen")

    def stop(self) -> None:
        self._timer.stop()

    def enable_drag(self, on: bool) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    on)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, on)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.10) % (2 * math.pi)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.moved.emit(self.pos())
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        # covers glow ring (≤17 px radius) + body below + label
        return QRectF(-18.0, -36.0, 36.0, 52.0)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        # ── Pulse glow ───────────────────────────────────────────
        glow_r     = 13.0 + 4.0 * math.sin(self._phase)
        glow_alpha = int(45 + 25 * math.sin(self._phase))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(79, 195, 247, glow_alpha)))
        painter.drawEllipse(QRectF(-glow_r, -glow_r, 2.0 * glow_r, 2.0 * glow_r))

        # ── Router body ──────────────────────────────────────────
        painter.setPen(QPen(QColor(160, 190, 220), 1.5))
        painter.setBrush(QBrush(QColor(35, 55, 75)))
        painter.drawRoundedRect(QRectF(-10.0, -4.0, 20.0, 10.0), 2.0, 2.0)

        # ── Antenna mast ─────────────────────────────────────────
        painter.setPen(QPen(QColor(190, 210, 230), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(0.0, -4.0), QPointF(0.0, -18.0))

        # ── WiFi arcs (centered on mast top, opening upward) ─────
        # Qt angles: 0° = 3 o'clock, CCW. 210°→330° = upward cap.
        for i, r in enumerate([5.0, 9.0, 13.0]):
            alpha = 230 - i * 50
            painter.setPen(QPen(QColor(79, 195, 247, alpha), 1.5))
            painter.drawArc(
                QRectF(-r, -18.0 - r, 2.0 * r, 2.0 * r),
                210 * 16, 120 * 16,
            )

        # ── "Router" label ───────────────────────────────────────
        painter.setPen(QPen(QColor(210, 220, 240, 200)))
        fnt = painter.font()
        fnt.setPointSizeF(7.5)
        painter.setFont(fnt)
        painter.drawText(
            QRectF(-18.0, 8.0, 36.0, 12.0),
            Qt.AlignmentFlag.AlignHCenter,
            "Router",
        )


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
    30  snap indicator
    100 wifi measurements
    110 pending measure marker
    """

    zoom_changed         = Signal(float)   # zoom as % (10–500)
    pending_changed      = Signal(bool)    # True = pending marker placed
    measurement_selected = Signal(object)  # Measurement | None
    router_changed       = Signal(object)  # QPointF | None
    heatmap_computing    = Signal(bool)    # True while heatmap worker runs

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
        self.setMouseTracking(True)

        # ── Zoom / pan ─────────────────────────────────────────
        self._zoom_factor:   float   = 1.0
        self._pan_active:    bool    = False
        self._pan_origin:    QPointF = QPointF()
        self._space_pressed: bool    = False

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
        self._selected_item:        Optional[_ElementItem]     = None
        self._selected_measurement: Optional[Measurement]      = None

        # ── Snap settings ──────────────────────────────────────
        self._snap_grid:      bool = False
        self._snap_points:    bool = True
        self._grid_snap_size: int  = 20

        # ── Element registry ───────────────────────────────────
        self._element_items: dict[str, _ElementItem] = {}

        # ── Measurement state ──────────────────────────────────
        self._measurement_items: dict[int, _MeasurementItem] = {}  # id(m) → item
        self._pending_marker:    Optional[_PendingMarker]    = None
        self._pending_pos:       Optional[QPointF]           = None
        self._ssid_filter:       Optional[str]               = None
        self._min_dbm:           float = -90.0
        self._max_dbm:           float = -30.0

        # ── Router state ───────────────────────────────────────
        self._router_item:          Optional[_RouterItem]          = None
        self._router_line:          Optional[QGraphicsLineItem]    = None
        self._pre_drag_router_pos:  Optional[tuple[float, float]]  = None

        # ── Heatmap state ──────────────────────────────────────
        self._heatmap_overlay:  object           = None   # Optional[_HeatmapOverlay]
        self._heatmap_visible:  bool             = True
        self._heatmap_opacity:  int              = 50     # 0–100
        self._legend_pixmap:    Optional[QPixmap] = None   # cached

        # ── Undo / redo ────────────────────────────────────────
        self._undo_stack: Optional[QUndoStack] = None

        # ── Move-drag tracking ─────────────────────────────────
        self._pre_drag_elem_id: Optional[str]  = None
        self._pre_drag_pos:     Optional[dict] = None

    # ──────────────────────────────────────────────────────────
    # Public API — mode / display
    # ──────────────────────────────────────────────────────────

    def set_mode(self, mode: CanvasMode) -> None:
        if mode != CanvasMode.MEASURE and self._mode == CanvasMode.MEASURE:
            self._clear_pending_marker()
            self.pending_changed.emit(False)

        self._mode = mode
        interactive = (mode == CanvasMode.SELECT)

        for item in self._element_items.values():
            item.enable_interaction(interactive)
        for item in self._measurement_items.values():
            item.enable_selection(interactive)
        if self._router_item is not None:
            self._router_item.enable_drag(interactive)

        if not interactive:
            self._deselect()

        self._snap_indicator.setVisible(False)
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

    def set_dbm_range(self, min_dbm: float, max_dbm: float) -> None:
        self._min_dbm = min_dbm
        self._max_dbm = max_dbm
        self._legend_pixmap = None   # invalidate legend cache
        for item in self._measurement_items.values():
            item.update_color(min_dbm, max_dbm)
        if self._heatmap_overlay is not None:
            self._heatmap_overlay.set_dbm_range(min_dbm, max_dbm)
            self._heatmap_overlay.update_heatmap()
        self._scene.update()
        self.viewport().update()   # repaint legend

    def set_ssid_filter(self, ssid: Optional[str]) -> None:
        self._ssid_filter = ssid
        self._rebuild_scene()

    def set_heatmap_visible(self, visible: bool) -> None:
        self._heatmap_visible = visible
        if self._heatmap_overlay is not None:
            self._heatmap_overlay.setVisible(visible)
        self.viewport().update()   # repaint legend

    def set_heatmap_opacity(self, pct: int) -> None:
        self._heatmap_opacity = pct
        if self._heatmap_overlay is not None:
            self._heatmap_overlay.set_opacity_percent(pct)
            self._heatmap_overlay.update_heatmap()

    # ──────────────────────────────────────────────────────────
    # Public API — floor management
    # ──────────────────────────────────────────────────────────

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

    def set_undo_stack(self, stack: QUndoStack) -> None:
        self._undo_stack = stack

    def set_active_floor(self, floor: Floor) -> None:
        self._floor = floor
        self._rebuild_scene()

    # ──────────────────────────────────────────────────────────
    # Public API — measurement workflow
    # ──────────────────────────────────────────────────────────

    @property
    def pending_measure_pos(self) -> Optional[QPointF]:
        return self._pending_pos

    def place_pending_at(self, pos: QPointF) -> None:
        """Place (or move) the pending marker programmatically."""
        self._clear_pending_marker()
        marker = _PendingMarker()
        marker.setPos(pos)
        self._scene.addItem(marker)
        self._pending_marker = marker
        self._pending_pos    = pos
        self.pending_changed.emit(True)

    def place_measurement(self, m: Measurement) -> None:
        """Commit *m* as a permanent measurement, removing the pending marker."""
        self._clear_pending_marker()
        if self._floor is None:
            return
        self._floor.measurements.append(m)
        if self._ssid_filter is None or m.ssid == self._ssid_filter:
            item = _MeasurementItem(m, self._min_dbm, self._max_dbm)
            item.enable_selection(self._mode == CanvasMode.SELECT)
            self._scene.addItem(item)
            self._measurement_items[id(m)] = item
        self._push_cmd(AddMeasurementCommand(self._floor, m, self._rebuild_scene))
        self.pending_changed.emit(False)
        if self._heatmap_overlay is not None:
            self._heatmap_overlay.update_heatmap()

    def cancel_pending_measurement(self) -> None:
        self._clear_pending_marker()
        self.pending_changed.emit(False)

    def place_router(self, pos: QPointF) -> None:
        """Place (or move) the router icon to *pos* and save to the floor model."""
        if self._floor is None:
            return
        old_pos = self._floor.router_position
        new_pos = (pos.x(), pos.y())
        self._floor.router_position = new_pos
        self._push_cmd(SetRouterCommand(self._floor, old_pos, new_pos, self._rebuild_scene))
        self._restore_router()
        self.router_changed.emit(pos)

    def remove_router(self) -> None:
        """Remove the router from the current floor."""
        if self._floor is None:
            return
        old_pos = self._floor.router_position
        self._floor.router_position = None
        self._push_cmd(SetRouterCommand(self._floor, old_pos, None, self._rebuild_scene))
        if self._router_item is not None:
            self._router_item.stop()
            self._scene.removeItem(self._router_item)
            self._router_item = None
        self._update_router_line()
        self.router_changed.emit(None)

    def remove_measurement_item(self, m: Measurement) -> None:
        """Remove measurement *m* from scene and floor model."""
        item = self._measurement_items.pop(id(m), None)
        if item is not None:
            self._scene.removeItem(item)
        if self._floor is not None:
            self._floor.measurements = [
                x for x in self._floor.measurements if x is not m
            ]
        if self._selected_measurement is m:
            self._selected_measurement = None
            self.measurement_selected.emit(None)
        if self._floor is not None:
            self._push_cmd(RemoveMeasurementCommand(self._floor, m, self._rebuild_scene))
        if self._heatmap_overlay is not None:
            self._heatmap_overlay.update_heatmap()

    def scroll_to_measurement(self, m: Measurement) -> None:
        """Center the view on *m* and select it (switches to SELECT mode)."""
        item = self._measurement_items.get(id(m))
        if item is None:
            return
        if self._mode != CanvasMode.SELECT:
            self.set_mode(CanvasMode.SELECT)
        self.centerOn(item)
        self._scene.clearSelection()
        item.setSelected(True)

    # ──────────────────────────────────────────────────────────
    # Zoom
    # ──────────────────────────────────────────────────────────

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom_factor * factor))
        actual   = new_zoom / self._zoom_factor
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
        self._clear_pending_marker()
        if self._router_item is not None:
            self._router_item.stop()
        self._selected_item        = None
        self._selected_measurement = None

        _persistent = {self._grid_item, self._snap_indicator}
        for item in list(self._scene.items()):
            if item not in _persistent:
                self._scene.removeItem(item)

        self._bg_item = None
        self._bg_move_mode = False
        self._element_items.clear()
        self._measurement_items.clear()
        self._router_item     = None
        self._router_line     = None
        self._heatmap_overlay = None   # removed with scene; will be recreated below
        self._snap_indicator.setVisible(False)

        if self._floor is None:
            return
        if self._floor.background_image:
            self._load_bg_pixmap(self._floor.background_image)
        self._restore_elements()
        self._restore_measurements()
        self._restore_router()
        self._restore_heatmap()
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

    def _restore_measurements(self) -> None:
        if self._floor is None:
            return
        in_select = (self._mode == CanvasMode.SELECT)
        for m in self._floor.measurements:
            if self._ssid_filter is not None and m.ssid != self._ssid_filter:
                continue
            item = _MeasurementItem(m, self._min_dbm, self._max_dbm)
            item.enable_selection(in_select)
            self._scene.addItem(item)
            self._measurement_items[id(m)] = item

    def _restore_router(self) -> None:
        if self._floor is None or self._floor.router_position is None:
            return
        rx, ry = self._floor.router_position
        item = _RouterItem()
        item.setPos(rx, ry)
        item.enable_drag(self._mode == CanvasMode.SELECT)
        item.moved.connect(self._update_router_line)
        self._scene.addItem(item)
        self._router_item = item
        self._update_router_line()

    def _restore_heatmap(self) -> None:
        if _HeatmapOverlay is None or self._floor is None:
            return
        overlay = _HeatmapOverlay()
        overlay.setZValue(_Z_HEATMAP)
        overlay.setVisible(self._heatmap_visible)
        overlay.set_floor(self._floor)
        overlay.set_dbm_range(self._min_dbm, self._max_dbm)
        overlay.set_opacity_percent(self._heatmap_opacity)
        overlay.computing_changed.connect(self.heatmap_computing)
        self._scene.addItem(overlay)
        self._heatmap_overlay = overlay
        overlay.update_heatmap()

    def _make_rect_item(self, d: dict) -> _RectElement:
        item = _RectElement(QRectF(0.0, 0.0, d["w"], d["h"]), d["id"])
        item.setPos(d["x"], d["y"])
        return item

    def _make_line_item(self, d: dict) -> _LineElement:
        item = _LineElement(d["x2"] - d["x1"], d["y2"] - d["y1"], d["id"])
        item.setPos(d["x1"], d["y1"])
        return item

    # ──────────────────────────────────────────────────────────
    # Undo helpers
    # ──────────────────────────────────────────────────────────

    def _push_cmd(self, cmd) -> None:
        if self._undo_stack is not None:
            self._undo_stack.push(cmd)

    def _get_elem_model_pos(self, elem_id: str) -> Optional[dict]:
        if self._floor is None:
            return None
        for e in self._floor.elements:
            if e.get("id") == elem_id:
                if e.get("type") == "rect":
                    return {"x": e["x"], "y": e["y"]}
                return {"x1": e["x1"], "y1": e["y1"],
                        "x2": e["x2"], "y2": e["y2"]}
        return None

    # ──────────────────────────────────────────────────────────
    # Snap
    # ──────────────────────────────────────────────────────────

    def _do_snap(self, raw_scene_pt: QPointF) -> tuple[QPointF, SnapType]:
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
        self._push_cmd(AddElementCommand(self._floor, d, self._rebuild_scene))

    # ──────────────────────────────────────────────────────────
    # Measurement helpers
    # ──────────────────────────────────────────────────────────

    def _place_pending_marker(self, pos: QPointF) -> None:
        self._clear_pending_marker()
        marker = _PendingMarker()
        marker.setPos(pos)
        self._scene.addItem(marker)
        self._pending_marker = marker
        self._pending_pos    = pos
        self.pending_changed.emit(True)

    def _clear_pending_marker(self) -> None:
        if self._pending_marker is not None:
            self._pending_marker.stop()
            self._scene.removeItem(self._pending_marker)
            self._pending_marker = None
        self._pending_pos = None

    def _update_router_line(self, _: object = None) -> None:
        """Draw or update the dashed line from the selected measurement to the router."""
        if self._router_item is None or self._selected_measurement is None:
            if self._router_line is not None:
                self._scene.removeItem(self._router_line)
                self._router_line = None
            return
        m  = self._selected_measurement
        rp = self._router_item.pos()
        if self._router_line is None:
            pen = QPen(QColor(79, 195, 247, 140), 1.5, Qt.PenStyle.DashLine)
            pen.setDashPattern([6.0, 4.0])
            self._router_line = QGraphicsLineItem(m.x, m.y, rp.x(), rp.y())
            self._router_line.setPen(pen)
            self._router_line.setZValue(_Z_ROUTER_LINE)
            self._scene.addItem(self._router_line)
        else:
            self._router_line.setLine(m.x, m.y, rp.x(), rp.y())

    def _measurement_item_at(self, vp_pos: QPointF) -> Optional[_MeasurementItem]:
        for item in self.items(vp_pos.toPoint()):
            if isinstance(item, _MeasurementItem):
                return item
        return None

    # ──────────────────────────────────────────────────────────
    # Selection & deletion
    # ──────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        sel = self._scene.selectedItems()
        el  = [i for i in sel if isinstance(i, (_RectElement, _LineElement))]
        ms  = [i for i in sel if isinstance(i, _MeasurementItem)]

        self._selected_item        = el[0] if el else None
        prev_m = self._selected_measurement
        self._selected_measurement = ms[0].measurement if ms else None

        if self._selected_measurement is not prev_m:
            self.measurement_selected.emit(self._selected_measurement)
        self._update_router_line()

    def _deselect(self) -> None:
        self._scene.clearSelection()
        self._selected_item        = None
        self._selected_measurement = None

    def _element_item_at(self, vp_pos: QPointF) -> Optional[_ElementItem]:
        for item in self.items(vp_pos.toPoint()):
            if isinstance(item, (_RectElement, _LineElement)):
                return item
        return None

    def _delete_element_item(self, item: _ElementItem) -> None:
        eid = item.elem_id
        elem_dict: Optional[dict] = None
        if self._floor is not None:
            for e in self._floor.elements:
                if e.get("id") == eid:
                    elem_dict = e
                    break
            self._floor.elements = [
                e for e in self._floor.elements if e.get("id") != eid
            ]
        self._element_items.pop(eid, None)
        if item is self._selected_item:
            self._selected_item = None
        self._scene.removeItem(item)
        if elem_dict is not None and self._floor is not None:
            self._push_cmd(RemoveElementCommand(self._floor, elem_dict, self._rebuild_scene))

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
        # Router context menu takes priority over background menu
        if self._router_item is not None:
            for _it in self.items(event.pos()):
                if _it is self._router_item:
                    menu = QMenu(self)
                    menu.setStyleSheet(self._MENU_STYLE)
                    menu.addAction("Router entfernen").triggered.connect(self.remove_router)
                    menu.exec(event.globalPosition().toPoint())
                    return

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
        assert self._floor is not None
        old_state = (self._floor.background_image, self._floor.bg_offset,
                     self._floor.bg_scale)
        if self._bg_item is not None:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        self._floor.background_image = path
        self._floor.bg_offset = (0.0, 0.0)
        self._floor.bg_scale  = 1.0
        self._load_bg_pixmap(path)
        self._push_cmd(SetBackgroundCommand(
            self._floor, old_state, (path, (0.0, 0.0), 1.0), self._rebuild_scene,
        ))

    def _scale_bg(self) -> None:
        if self._floor is None or self._bg_item is None:
            return
        dlg = _ImageScaleDialog(self._floor.bg_scale, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        old_state = (self._floor.background_image, self._floor.bg_offset,
                     self._floor.bg_scale)
        self._floor.bg_scale = dlg.scale
        self._bg_item.setScale(dlg.scale)
        self._push_cmd(SetBackgroundCommand(
            self._floor, old_state,
            (self._floor.background_image, self._floor.bg_offset, dlg.scale),
            self._rebuild_scene,
        ))

    def _toggle_bg_move(self) -> None:
        self._bg_move_mode = not self._bg_move_mode
        if self._bg_item is not None:
            self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                                  self._bg_move_mode)
            self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                                  self._bg_move_mode)
        self._update_cursor()

    def _remove_bg(self) -> None:
        if self._floor is None:
            return
        old_state = (self._floor.background_image, self._floor.bg_offset,
                     self._floor.bg_scale)
        if self._bg_item is not None:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        self._floor.background_image = None
        self._floor.bg_offset = (0.0, 0.0)
        self._floor.bg_scale  = 1.0
        self._bg_move_mode = False
        self._update_cursor()
        self._push_cmd(SetBackgroundCommand(
            self._floor, old_state, (None, (0.0, 0.0), 1.0), self._rebuild_scene,
        ))

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
            if self._mode == CanvasMode.MEASURE:
                self._clear_pending_marker()
                self.pending_changed.emit(False)
            event.accept()
        elif k == Qt.Key.Key_Delete and not event.isAutoRepeat():
            if self._mode == CanvasMode.SELECT:
                if self._selected_item is not None:
                    self._delete_element_item(self._selected_item)
                elif self._selected_measurement is not None:
                    self.remove_measurement_item(self._selected_measurement)
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

        raw_pt             = self.mapToScene(event.position().toPoint())
        snapped, snap_type = self._do_snap(raw_pt)

        if self._mode == CanvasMode.RECT:
            self._snap_indicator.update_snap(snapped, snap_type)
            self._start_rect(snapped)
            event.accept()

        elif self._mode == CanvasMode.LINE:
            self._snap_indicator.update_snap(snapped, snap_type)
            self._start_line(snapped)
            event.accept()

        elif self._mode == CanvasMode.MEASURE:
            self._place_pending_marker(raw_pt)
            event.accept()

        elif self._mode == CanvasMode.ROUTER:
            self.place_router(raw_pt)
            event.accept()

        elif self._mode == CanvasMode.SELECT:
            # Pre-record router position in case this starts a drag
            self._pre_drag_router_pos = None
            if self._router_item is not None:
                for _it in self.items(event.position().toPoint()):
                    if _it is self._router_item:
                        _p = self._router_item.pos()
                        self._pre_drag_router_pos = (_p.x(), _p.y())
                        break
            hit = self._element_item_at(event.position())
            if hit is not None:
                self._pre_drag_elem_id = hit.elem_id
                self._pre_drag_pos     = self._get_elem_model_pos(hit.elem_id)
            else:
                self._pre_drag_elem_id = None
                self._pre_drag_pos     = None
            super().mousePressEvent(event)

        elif self._mode == CanvasMode.DELETE:
            hit_el = self._element_item_at(event.position())
            if hit_el is not None:
                self._delete_element_item(hit_el)
            else:
                hit_m = self._measurement_item_at(event.position())
                if hit_m is not None:
                    self.remove_measurement_item(hit_m.measurement)
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

        # ── Draw modes — snap indicator ────────────────────────
        if self._mode in _DRAW_MODES:
            raw_pt             = self.mapToScene(event.position().toPoint())
            snapped, snap_type = self._do_snap(raw_pt)
            self._snap_indicator.update_snap(snapped, snap_type)
            if self._draw_start is not None:
                self._update_preview(snapped)
            event.accept()
            return

        self._snap_indicator.setVisible(False)
        super().mouseMoveEvent(event)

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
                self._snap_indicator.update_snap(snapped, snap_type)
                event.accept()
                return

        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == CanvasMode.SELECT and self._selected_item is not None:
                self._sync_item_to_model(self._selected_item)
                if (self._pre_drag_elem_id is not None
                        and self._pre_drag_pos is not None
                        and self._floor is not None):
                    new_pos = self._get_elem_model_pos(self._pre_drag_elem_id)
                    if new_pos is not None and new_pos != self._pre_drag_pos:
                        self._push_cmd(MoveElementCommand(
                            self._floor, self._pre_drag_elem_id,
                            self._pre_drag_pos, new_pos, self._rebuild_scene,
                        ))
                self._pre_drag_elem_id = None
                self._pre_drag_pos     = None
            # Sync router drag → floor model + undo command
            if (self._mode == CanvasMode.SELECT
                    and self._pre_drag_router_pos is not None
                    and self._router_item is not None
                    and self._floor is not None):
                new_p   = self._router_item.pos()
                new_tup = (new_p.x(), new_p.y())
                if new_tup != self._pre_drag_router_pos:
                    self._floor.router_position = new_tup
                    self._push_cmd(SetRouterCommand(
                        self._floor, self._pre_drag_router_pos, new_tup,
                        self._rebuild_scene,
                    ))
                    self.router_changed.emit(new_p)
                    self._update_router_line()
            self._pre_drag_router_pos = None
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

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Paint the dBm legend in the top-right corner of the viewport."""
        if not self._heatmap_visible:
            return
        if self._floor is None or not self._floor.measurements:
            return

        if self._legend_pixmap is None:
            self._legend_pixmap = create_legend_gradient(
                80, 160, self._min_dbm, self._max_dbm
            )
        px = self._legend_pixmap
        painter.save()
        painter.resetTransform()   # switch from scene → viewport coordinates
        vp = self.viewport()
        painter.drawPixmap(vp.width() - px.width() - 8, 8, px)
        painter.restore()
