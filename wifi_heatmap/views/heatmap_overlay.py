from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from PySide6.QtCore import QObject, QPointF, QRectF, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from models.floor import Floor
from services.interpolation import HeatmapGenerator


_RESOLUTION = 5     # scene units per interpolation sample
_MARGIN     = 200   # scene units of padding around measurement bounding box


# ──────────────────────────────────────────────────────────────────────────────
# Background worker
# ──────────────────────────────────────────────────────────────────────────────

class _HeatmapWorker(QThread):
    """Runs HeatmapGenerator in a background thread."""

    # (QImage, scene_x, scene_y, generation_id)
    result_ready = Signal(object, float, float, int)

    def __init__(
        self,
        measurements: list,
        x0: float,
        y0: float,
        width: int,
        height: int,
        min_dbm: float,
        max_dbm: float,
        opacity: float,
        generation: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ms       = measurements
        self._x0       = x0
        self._y0       = y0
        self._width    = width
        self._height   = height
        self._min_dbm  = min_dbm
        self._max_dbm  = max_dbm
        self._opacity  = opacity
        self._gen      = generation

    def run(self) -> None:
        try:
            # Shift measurement coordinates to local (0 … w, 0 … h) space
            local = [
                SimpleNamespace(x=m.x - self._x0, y=m.y - self._y0, dbm=m.dbm)
                for m in self._ms
            ]
            gen  = HeatmapGenerator()
            grid = gen.generate(local, self._width, self._height, _RESOLUTION)
            img  = gen.generate_image(
                grid,
                self._min_dbm, self._max_dbm, self._opacity,
                target_width=self._width,
                target_height=self._height,
            )
            self.result_ready.emit(img, self._x0, self._y0, self._gen)
        except Exception:
            pass   # keep old pixmap on error; no crash


# ──────────────────────────────────────────────────────────────────────────────
# Overlay item
# ──────────────────────────────────────────────────────────────────────────────

class HeatmapOverlay(QGraphicsObject):
    """QGraphicsObject that shows an interpolated WiFi signal heatmap.

    Uses QGraphicsObject (inherits QObject + QGraphicsItem) so it can emit
    signals and own a QThread without a separate emitter helper.

    Z-value is fixed at 5 — between the grid (1) and drawing elements (10).
    """

    computing_changed = Signal(bool)   # True while worker is running

    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(5)   # _Z_HEATMAP

        self._pixmap:  QPixmap = QPixmap()
        self._px_pos:  QPointF = QPointF(0.0, 0.0)   # where the pixmap starts
        self._floor:   Optional[Floor] = None
        self._min_dbm: float = -90.0
        self._max_dbm: float = -30.0
        self._opacity: float = 0.5    # 0.0 – 1.0
        self._gen:     int   = 0      # generation counter — ignores stale results
        self._worker:  Optional[_HeatmapWorker] = None

    # ── QGraphicsItem interface ─────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        p = self._px_pos
        return QRectF(p.x(), p.y(),
                      float(self._pixmap.width()), float(self._pixmap.height()))

    def paint(self, painter, option, widget=None) -> None:
        if not self._pixmap.isNull():
            painter.drawPixmap(self._px_pos, self._pixmap)

    # ── Public setters ──────────────────────────────────────────────────────

    def set_floor(self, floor: Optional[Floor]) -> None:
        self._floor = floor

    def set_dbm_range(self, min_dbm: float, max_dbm: float) -> None:
        self._min_dbm = min_dbm
        self._max_dbm = max_dbm

    def set_opacity_percent(self, pct: int) -> None:
        self._opacity = max(0.0, min(1.0, pct / 100.0))

    # ── Heatmap computation ─────────────────────────────────────────────────

    def update_heatmap(self) -> None:
        """Start an async heatmap recalculation for the current floor."""
        if self._floor is None:
            return
        ms = list(self._floor.measurements)
        if not ms:
            self._set_empty()
            return

        # Bounding box in scene coords + margin
        xs = [m.x for m in ms]
        ys = [m.y for m in ms]
        x0 = min(xs) - _MARGIN
        y0 = min(ys) - _MARGIN
        w  = max(int(max(xs) - x0 + _MARGIN), 1)
        h  = max(int(max(ys) - y0 + _MARGIN), 1)

        self._gen += 1
        gen = self._gen

        worker = _HeatmapWorker(
            ms, x0, y0, w, h,
            self._min_dbm, self._max_dbm, self._opacity, gen,
        )
        worker.result_ready.connect(self._on_result)
        worker.finished.connect(lambda: self._on_finished(gen))
        self._worker = worker
        self.computing_changed.emit(True)
        worker.start()

    # ── Private slots ───────────────────────────────────────────────────────

    def _on_result(self, img: QImage, x0: float, y0: float, gen: int) -> None:
        if gen != self._gen:
            return   # stale — a newer calculation is in flight
        self.prepareGeometryChange()
        self._pixmap = QPixmap.fromImage(img)
        self._px_pos = QPointF(x0, y0)
        self.update()

    def _on_finished(self, gen: int) -> None:
        if gen == self._gen:
            self.computing_changed.emit(False)

    def _set_empty(self) -> None:
        self.prepareGeometryChange()
        self._pixmap = QPixmap()
        self._px_pos = QPointF(0.0, 0.0)
        self.update()
