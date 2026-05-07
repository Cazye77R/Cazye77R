from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CanvasWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.StrongFocus)

        self._bg_color = QColor("#1e1e2e")
        self._grid_color = QColor("#2a2a3a")
        self._show_grid: bool = False

    def set_show_grid(self, show: bool) -> None:
        self._show_grid = show
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)
        if self._show_grid:
            self._draw_grid(painter)
        painter.end()

    def _draw_grid(self, painter: QPainter) -> None:
        painter.setPen(QPen(self._grid_color, 1))
        step = 20
        w, h = self.width(), self.height()
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)
