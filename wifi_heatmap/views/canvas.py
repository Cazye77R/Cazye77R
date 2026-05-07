from __future__ import annotations

import enum
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
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


class CanvasMode(enum.Enum):
    SELECT = "select"
    RECT = "rect"
    LINE = "line"
    ROUTER = "router"
    MEASURE = "measure"
    DELETE = "delete"


_ZOOM_MIN: float = 0.10
_ZOOM_MAX: float = 5.00
_ZOOM_STEP: float = 1.15  # multiplicative factor per scroll notch

# Z-layer ordering — image < grid < elements < measurements
_Z_BACKGROUND: int = 0
_Z_GRID: int = 1
_Z_ELEMENTS: int = 10
_Z_MEASUREMENTS: int = 100


class _GridItem(QGraphicsItem):
    """Infinite cosmetic grid rendered above the background image but below elements."""

    def __init__(self, grid_size: int = 20) -> None:
        super().__init__()
        self._grid_size = grid_size
        # pen width=0 → cosmetic: always 1 pixel regardless of zoom level
        self._pen = QPen(QColor(55, 55, 75), 0)
        self.setZValue(_Z_GRID)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def set_grid_size(self, size: int) -> None:
        self._grid_size = size
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-100_000.0, -100_000.0, 200_000.0, 200_000.0)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        rect = option.exposedRect
        gs = float(self._grid_size)
        painter.setPen(self._pen)

        # Snap start coordinates to grid
        left = int(rect.left() / gs) * gs
        top = int(rect.top() / gs) * gs

        x = left
        while x <= rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += gs

        y = top
        while y <= rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += gs


class _ImageScaleDialog(QDialog):
    """Modal dialog with a slider + spin box for background image scale (10 %–500 %)."""

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

        self._slider = QSlider(Qt.Horizontal)
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

        # Connect after setting initial values to suppress startup signals
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)
        self._refresh_label(int(self._scale * 100))

    def _refresh_label(self, value: int) -> None:
        self._pct_label.setText(f"{value} %")

    def _on_slider(self, value: int) -> None:
        self._scale = value / 100.0
        self._refresh_label(value)
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)

    def _on_spin(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self._scale = value / 100.0
        self._refresh_label(value)

    @property
    def scale(self) -> float:
        return self._scale


class CanvasWidget(QGraphicsView):
    """
    Main canvas based on QGraphicsView + QGraphicsScene.

    Layers (bottom to top):
        Z=0   background image (QGraphicsPixmapItem)
        Z=1   grid overlay (_GridItem)
        Z=10  drawing elements (rect / line)
        Z=100 wifi measurements
    """

    zoom_changed = Signal(float)  # payload: current zoom as % (10.0 – 500.0)

    _MENU_STYLE = (
        "QMenu { background-color: #2a2a3a; color: #e0e0e0;"
        "        border: 1px solid #3a3a4a; }"
        "QMenu::item { padding: 4px 20px 4px 10px; }"
        "QMenu::item:selected { background-color: #4fc3f7; color: #1e1e2e; }"
        "QMenu::separator { height: 1px; background: #3a3a4a; margin: 4px 0; }"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # --- Scene ---
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-5_000.0, -5_000.0, 10_000.0, 10_000.0)
        self._scene.setBackgroundBrush(QBrush(QColor("#1e1e2e")))
        # NoIndex avoids BSP overhead from the large-bounding-rect grid item
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self._scene)

        # Grid item persists across floor switches
        self._grid_item = _GridItem()
        self._grid_item.setVisible(False)
        self._scene.addItem(self._grid_item)

        # --- View settings ---
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
        self.setStyleSheet("QGraphicsView { background-color: #1e1e2e; border: none; }")

        # --- Interaction state ---
        self._zoom_factor: float = 1.0
        self._pan_active: bool = False
        self._pan_origin: QPointF = QPointF()
        self._space_pressed: bool = False

        # --- Tool mode ---
        self._mode: CanvasMode = CanvasMode.SELECT

        # --- Floor management ---
        self._floor: Optional[Floor] = None
        self._floors: dict[int, Floor] = {}  # tab_index → Floor

        # --- Background image ---
        self._bg_item: Optional[QGraphicsPixmapItem] = None
        self._bg_move_mode: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_mode(self, mode: CanvasMode) -> None:
        self._mode = mode
        self._update_cursor()

    def set_show_grid(self, show: bool) -> None:
        self._grid_item.setVisible(show)

    def set_grid_size(self, size: int) -> None:
        self._grid_item.set_grid_size(size)

    def load_floor(self, index: int) -> None:
        """Activate the floor at *index*, creating a bare Floor if it doesn't exist yet."""
        if index not in self._floors:
            name = "Erdgeschoss" if index == 0 else f"Etage {index}"
            self._floors[index] = Floor(name=name, level=index)
        self._floor = self._floors[index]
        self._rebuild_scene()

    def register_floor(self, index: int, floor: Floor) -> None:
        """Inject an externally managed Floor (e.g. loaded from a project file)."""
        self._floors[index] = floor
        if self._floor is None or index == 0:
            self.load_floor(index)

    def current_floor(self) -> Optional[Floor]:
        return self._floor

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom_factor * factor))
        actual = new_zoom / self._zoom_factor
        if abs(actual - 1.0) < 1e-9:
            return
        self._zoom_factor = new_zoom
        self.scale(actual, actual)  # AnchorUnderMouse is respected here
        self.zoom_changed.emit(self._zoom_factor * 100.0)

    # ------------------------------------------------------------------
    # Scene rebuild
    # ------------------------------------------------------------------

    def _rebuild_scene(self) -> None:
        """Remove all non-persistent items and reload content from the current Floor."""
        for item in list(self._scene.items()):
            if item is not self._grid_item:
                self._scene.removeItem(item)
        self._bg_item = None
        self._bg_move_mode = False

        if self._floor is None:
            return
        if self._floor.background_image:
            self._load_bg_pixmap(self._floor.background_image)

        # TODO: restore self._floor.elements (rect / line items)
        # TODO: restore self._floor.measurements

        self._update_cursor()

    def _load_bg_pixmap(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        item = QGraphicsPixmapItem(pixmap)
        item.setZValue(_Z_BACKGROUND)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        if self._floor:
            ox, oy = self._floor.bg_offset
            item.setPos(ox, oy)
            item.setScale(self._floor.bg_scale)
        self._scene.addItem(item)
        self._bg_item = item

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._MENU_STYLE)

        load_act = menu.addAction("Hintergrundbild laden …")
        load_act.triggered.connect(self._load_background_image)

        if self._bg_item is not None:
            menu.addSeparator()
            scale_act = menu.addAction("Bild skalieren …")
            scale_act.triggered.connect(self._scale_background_image)

            move_label = (
                "Bild verschieben beenden" if self._bg_move_mode else "Bild verschieben"
            )
            move_act = menu.addAction(move_label)
            move_act.triggered.connect(self._toggle_bg_move_mode)

            menu.addSeparator()
            remove_act = menu.addAction("Hintergrundbild entfernen")
            remove_act.triggered.connect(self._remove_background_image)

        menu.exec(event.globalPosition().toPoint())

    # ------------------------------------------------------------------
    # Background image actions
    # ------------------------------------------------------------------

    def _load_background_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Hintergrundbild laden",
            "",
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
        self._floor.bg_scale = 1.0
        self._load_bg_pixmap(path)

    def _scale_background_image(self) -> None:
        if self._floor is None or self._bg_item is None:
            return
        dlg = _ImageScaleDialog(self._floor.bg_scale, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._floor.bg_scale = dlg.scale
        self._bg_item.setScale(dlg.scale)

    def _toggle_bg_move_mode(self) -> None:
        self._bg_move_mode = not self._bg_move_mode
        if self._bg_item is not None:
            movable = self._bg_move_mode
            self._bg_item.setFlag(QGraphicsItem.ItemIsMovable, movable)
            self._bg_item.setFlag(QGraphicsItem.ItemIsSelectable, movable)
        self._update_cursor()

    def _remove_background_image(self) -> None:
        if self._bg_item is not None:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        if self._floor is not None:
            self._floor.background_image = None
            self._floor.bg_offset = (0.0, 0.0)
            self._floor.bg_scale = 1.0
        self._bg_move_mode = False
        self._update_cursor()

    # ------------------------------------------------------------------
    # Event overrides — zoom, pan, keyboard
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = _ZOOM_STEP if delta > 0 else (1.0 / _ZOOM_STEP)
            self._apply_zoom(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
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
        is_middle = event.button() == Qt.MouseButton.MiddleButton
        is_space_left = (
            self._space_pressed and event.button() == Qt.MouseButton.LeftButton
        )
        if is_middle or is_space_left:
            self._pan_active = True
            self._pan_origin = event.position()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
        super().mouseMoveEvent(event)
        # Keep Floor.bg_offset in sync while dragging the background image
        if (
            self._bg_move_mode
            and self._bg_item is not None
            and self._floor is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            p = self._bg_item.pos()
            self._floor.bg_offset = (p.x(), p.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_active and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        ):
            self._pan_active = False
            self._update_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        # Final sync of offset once drag ends
        if (
            self._bg_move_mode
            and self._bg_item is not None
            and self._floor is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            p = self._bg_item.pos()
            self._floor.bg_offset = (p.x(), p.y())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_cursor(self) -> None:
        if self._bg_move_mode:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            return
        if self._space_pressed:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            return
        cursor_map: dict[CanvasMode, Qt.CursorShape] = {
            CanvasMode.SELECT: Qt.CursorShape.ArrowCursor,
            CanvasMode.RECT: Qt.CursorShape.CrossCursor,
            CanvasMode.LINE: Qt.CursorShape.CrossCursor,
            CanvasMode.ROUTER: Qt.CursorShape.CrossCursor,
            CanvasMode.MEASURE: Qt.CursorShape.CrossCursor,
            CanvasMode.DELETE: Qt.CursorShape.ForbiddenCursor,
        }
        self.setCursor(QCursor(cursor_map.get(self._mode, Qt.CursorShape.ArrowCursor)))
