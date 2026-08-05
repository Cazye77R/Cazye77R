from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from models.floor import Floor
from models.measurement import Measurement


_STRIP_HEIGHT = 80
_LEFT_MARGIN  = 72    # reserved for floor name label
_RIGHT_MARGIN = 10
_DOT_RADIUS   = 4
_ROUTER_MAST  = 14    # mast height in px
_ROUTER_ARC_R = (4, 8)

_COLOR_BG_EVEN     = QColor(0x2a, 0x2a, 0x3a)
_COLOR_BG_ODD      = QColor(0x24, 0x24, 0x34)
_COLOR_BORDER      = QColor(0x3a, 0x3a, 0x4a)
_COLOR_LABEL       = QColor(0xb0, 0xb8, 0xd0)
_COLOR_LEVEL       = QColor(0x60, 0x60, 0x80)
_COLOR_ROUTER_LINE = QColor(0x4f, 0xc3, 0xf7, 140)
_COLOR_ROUTER      = QColor(0x4f, 0xc3, 0xf7)
_COLOR_ELEM_BOX    = QColor(0x50, 0x50, 0x72, 100)


def _dbm_color(dbm: float, lo: float, hi: float) -> QColor:
    t = max(0.0, min(1.0, (dbm - lo) / max(hi - lo, 1.0)))
    if t <= 0.5:
        r, g = 255, int(t / 0.5 * 255)
    else:
        r, g = int((1.0 - (t - 0.5) / 0.5) * 255), 255
    return QColor(r, g, 0, 220)


class SideView(QWidget):
    """Dockable cross-section panel: all floors stacked bottom-to-top."""

    measurement_clicked = Signal(object, object)   # (Floor, Measurement)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #2a2a3a;")
        self.setMouseTracking(True)
        self.setMinimumWidth(200)

        self._floors:  list[Floor] = []
        self._min_dbm: float = -90.0
        self._max_dbm: float = -30.0
        self._x_min:   float = 0.0
        self._x_max:   float = 1000.0
        # Temporarily overridden during render_to_image() for off-screen painting
        self._render_w: Optional[int] = None

    # ── Public API ───────────────────────────────────────────────────

    def set_project(
        self,
        floors: list[Floor],
        min_dbm: float = -90.0,
        max_dbm: float = -30.0,
    ) -> None:
        self._floors  = list(floors)
        self._min_dbm = min_dbm
        self._max_dbm = max_dbm
        self._recalc_x_range()
        self._update_height()
        self.update()

    def set_dbm_range(self, min_dbm: float, max_dbm: float) -> None:
        self._min_dbm = min_dbm
        self._max_dbm = max_dbm
        self.update()

    def refresh(self) -> None:
        """Re-read floor data and repaint (call after in-place model changes)."""
        self._recalc_x_range()
        self._update_height()
        self.update()

    def render_to_image(self) -> QImage:
        """Render all floors at full height to a QImage (for PDF/export).

        Works independently of the widget's current on-screen size; uses the
        widget width as the render width (minimum 400 px).
        """
        n       = max(len(self._floors), 1)
        rw      = max(self.width(), 400)
        rh      = n * _STRIP_HEIGHT
        img     = QImage(rw, rh, QImage.Format.Format_RGB32)
        img.fill(QColor(0x2a, 0x2a, 0x3a))

        self._render_w = rw
        try:
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            floors = self._sorted_floors()
            n_f    = len(floors)
            global_rx: Optional[float] = next(
                (f.router_position[0] for f in floors if f.router_position), None
            )
            for i, floor in enumerate(floors):
                self._draw_strip(p, self._strip_rect(i, n_f), floor, i)
            if global_rx is not None:
                wx = self._to_wx(global_rx)
                p.setPen(QPen(_COLOR_ROUTER_LINE, 1.5, Qt.PenStyle.DashLine))
                p.drawLine(wx, 0, wx, n_f * _STRIP_HEIGHT)
            p.end()
        finally:
            self._render_w = None

        return img

    # ── Layout helpers ───────────────────────────────────────────────

    def _sorted_floors(self) -> list[Floor]:
        return sorted(self._floors, key=lambda f: f.level)

    def _recalc_x_range(self) -> None:
        xs: list[float] = []
        for f in self._floors:
            for m in f.measurements:
                xs.append(m.x)
            if f.router_position:
                xs.append(f.router_position[0])
        if len(xs) >= 2:
            span = max(xs) - min(xs)
            pad  = span * 0.08 + 40.0
            self._x_min = min(xs) - pad
            self._x_max = max(xs) + pad
        elif len(xs) == 1:
            self._x_min = xs[0] - 200.0
            self._x_max = xs[0] + 200.0
        else:
            self._x_min = 0.0
            self._x_max = 1000.0

    def _update_height(self) -> None:
        n = max(len(self._floors), 1)
        self.setMinimumHeight(n * _STRIP_HEIGHT)

    def _cw(self) -> int:
        w = self._render_w if self._render_w is not None else self.width()
        return max(w - _LEFT_MARGIN - _RIGHT_MARGIN, 1)

    def _to_wx(self, scene_x: float) -> int:
        span = max(self._x_max - self._x_min, 1.0)
        return int(_LEFT_MARGIN + (scene_x - self._x_min) / span * self._cw())

    def _strip_rect(self, strip_idx: int, n_floors: int) -> QRect:
        w = self._render_w if self._render_w is not None else self.width()
        y = (n_floors - 1 - strip_idx) * _STRIP_HEIGHT
        return QRect(0, y, w, _STRIP_HEIGHT)

    # ── Paint ────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        floors = self._sorted_floors()
        n = len(floors)
        if n == 0:
            painter.fillRect(self.rect(), _COLOR_BG_EVEN)
            painter.end()
            return

        for i, floor in enumerate(floors):
            self._draw_strip(painter, self._strip_rect(i, n), floor, i)

        # Global vertical router line across all strips
        global_rx: Optional[float] = next(
            (f.router_position[0] for f in floors if f.router_position), None
        )
        if global_rx is not None:
            wx = self._to_wx(global_rx)
            painter.setPen(QPen(_COLOR_ROUTER_LINE, 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(wx, 0, wx, n * _STRIP_HEIGHT)

        painter.end()

    def _draw_strip(
        self, painter: QPainter, rect: QRect, floor: Floor, idx: int
    ) -> None:
        bg = _COLOR_BG_EVEN if idx % 2 == 0 else _COLOR_BG_ODD
        painter.fillRect(rect, bg)

        # Top separator
        painter.setPen(QPen(_COLOR_BORDER, 1))
        painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())

        # Floor name
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(_COLOR_LABEL))
        painter.drawText(
            QRect(4, rect.top() + 4, _LEFT_MARGIN - 8, rect.height() - 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            floor.name,
        )

        # Level badge at bottom-left
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QPen(_COLOR_LEVEL))
        painter.drawText(
            QRect(4, rect.bottom() - 14, _LEFT_MARGIN - 8, 12),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Lvl {floor.level}",
        )

        # Element bounding box outline
        self._draw_elem_box(painter, rect, floor)

        # Measurement dots
        cy = rect.top() + rect.height() // 2
        for m in floor.measurements:
            self._draw_dot(painter, self._to_wx(m.x), cy, m)

        # Per-floor router icon (only on its own strip)
        if floor.router_position:
            self._draw_router(painter, rect, floor.router_position[0])

    def _draw_elem_box(
        self, painter: QPainter, rect: QRect, floor: Floor
    ) -> None:
        xs: list[float] = []
        ys: list[float] = []
        for e in floor.elements:
            t = e.get("type")
            if t == "rect":
                x, y = float(e["x"]), float(e["y"])
                w, h = float(e.get("w", 0)), float(e.get("h", 0))
                xs += [x, x + w]
                ys += [y, y + h]
            elif t == "line":
                xs += [float(e["x1"]), float(e["x2"])]
                ys += [float(e["y1"]), float(e["y2"])]
        if not xs:
            return
        wx1 = self._to_wx(min(xs))
        wx2 = self._to_wx(max(xs))
        wy1 = rect.top() + 8
        wy2 = rect.bottom() - 8
        painter.setPen(QPen(_COLOR_ELEM_BOX, 1, Qt.PenStyle.DotLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(wx1, wy1, max(wx2 - wx1, 4), wy2 - wy1))

    def _draw_dot(
        self, painter: QPainter, wx: int, cy: int, m: Measurement
    ) -> None:
        color = _dbm_color(m.dbm, self._min_dbm, self._max_dbm)
        r = _DOT_RADIUS
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(wx - r, cy - r, r * 2, r * 2)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 0.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(wx - r, cy - r, r * 2, r * 2)

    def _draw_router(
        self, painter: QPainter, rect: QRect, scene_x: float
    ) -> None:
        wx     = self._to_wx(scene_x)
        base_y = rect.bottom() - 6
        top_y  = base_y - _ROUTER_MAST

        painter.setPen(QPen(_COLOR_ROUTER, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(wx, base_y, wx, top_y)

        for r in _ROUTER_ARC_R:
            painter.drawArc(
                QRectF(wx - r, top_y - r, r * 2, r * 2),
                30 * 16, 120 * 16,
            )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_COLOR_ROUTER))
        painter.drawEllipse(wx - 2, base_y - 2, 4, 4)

    # ── Mouse events ─────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._hit_test(event.pos())
        if hit is not None:
            self.measurement_clicked.emit(*hit)

    def mouseMoveEvent(self, event) -> None:
        hit = self._hit_test(event.pos())
        if hit is not None:
            floor, m = hit
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{m.ssid or '—'}  {m.dbm:+.1f} dBm\nEtage: {floor.name}",
                self,
            )
        else:
            QToolTip.hideText()

    def _hit_test(
        self, pos: QPoint
    ) -> Optional[tuple[Floor, Measurement]]:
        floors = self._sorted_floors()
        n = len(floors)
        R = _DOT_RADIUS + 5
        for i, floor in enumerate(floors):
            rect = self._strip_rect(i, n)
            if not rect.contains(pos):
                continue
            cy = rect.top() + rect.height() // 2
            for m in floor.measurements:
                wx = self._to_wx(m.x)
                if abs(wx - pos.x()) <= R and abs(cy - pos.y()) <= R:
                    return floor, m
        return None
