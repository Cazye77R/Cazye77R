from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)

PALETTE: dict[str, str] = {
    "background": "#1e1e2e",
    "panel": "#2a2a3a",
    "text": "#e0e0e0",
    "accent": "#4fc3f7",
    "border": "#3a3a4a",
    "muted": "#606070",
}

# (dbm threshold, color) — ordered best to worst signal (legacy lookup table)
SIGNAL_GRADIENT: list[tuple[int, QColor]] = [
    (-50,  QColor(0,   200, 100)),
    (-65,  QColor(150, 220, 50)),
    (-75,  QColor(255, 200, 0)),
    (-85,  QColor(255, 100, 0)),
    (-100, QColor(200, 0,   0)),
]


def dbm_to_color(
    dbm: float,
    min_dbm: float = -90.0,
    max_dbm: float = -30.0,
) -> QColor:
    """Map *dbm* to a color on a red → yellow → green gradient.

    Values at or below *min_dbm* are dark red; at or above *max_dbm* are
    strong green.  The midpoint (-60 dBm with default range) is yellow.
    """
    if dbm <= min_dbm:
        return QColor(160, 0, 0)      # dark red — no signal
    if dbm >= max_dbm:
        return QColor(0, 210, 60)     # strong green — excellent

    t = (dbm - min_dbm) / (max_dbm - min_dbm)   # 0.0 = worst, 1.0 = best
    if t <= 0.5:
        f = t / 0.5
        return QColor(255, int(255 * f), 0)       # red → yellow
    else:
        f = (t - 0.5) / 0.5
        return QColor(int(255 * (1.0 - f)), 255, 0)  # yellow → green


def dbm_to_percent(dbm: float) -> int:
    """Convert dBm (-100 … -50) to 0–100 %."""
    clamped = max(-100.0, min(-50.0, dbm))
    return int(2 * (clamped + 100))


def create_legend_gradient(
    width: int = 80,
    height: int = 160,
    min_dbm: float = -90.0,
    max_dbm: float = -30.0,
) -> QPixmap:
    """Return a QPixmap with a vertical color bar and dBm labels.

    The bar runs from *min_dbm* (bottom, red) to *max_dbm* (top, green).
    """
    px = QPixmap(width, height)
    px.fill(QColor("#2a2a3a"))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    bar_w = 16
    bar_x = 2.0
    bar_y = 4.0
    bar_h = float(height - 8)

    # Vertical gradient: bottom = min (red), top = max (green)
    grad = QLinearGradient(0.0, bar_y + bar_h, 0.0, bar_y)
    steps = 24
    for i in range(steps + 1):
        t = i / steps
        grad.setColorAt(t, dbm_to_color(min_dbm + t * (max_dbm - min_dbm),
                                         min_dbm, max_dbm))
    p.fillRect(QRectF(bar_x, bar_y, float(bar_w), bar_h), grad)
    p.setPen(QPen(QColor(60, 60, 70), 1))
    p.drawRect(QRectF(bar_x, bar_y, float(bar_w), bar_h))

    # dBm labels at regular intervals
    font = QFont()
    font.setPointSize(8)
    p.setFont(font)
    p.setPen(QColor("#b0b0c8"))
    fm = p.fontMetrics()
    label_x = int(bar_x) + bar_w + 5
    num_ticks = 4
    for i in range(num_ticks + 1):
        t = i / num_ticks
        dbm_val = min_dbm + t * (max_dbm - min_dbm)
        # y increases downward; t=0 → bottom, t=1 → top
        y = int(bar_y + bar_h - t * bar_h)
        label = f"{dbm_val:.0f}"
        p.drawText(label_x, y + fm.ascent() // 2, label)

    p.end()
    return px
