from __future__ import annotations

from PySide6.QtGui import QColor

PALETTE: dict[str, str] = {
    "background": "#1e1e2e",
    "panel": "#2a2a3a",
    "text": "#e0e0e0",
    "accent": "#4fc3f7",
    "border": "#3a3a4a",
    "muted": "#606070",
}

# (dbm threshold, color) — ordered best to worst signal
SIGNAL_GRADIENT: list[tuple[int, QColor]] = [
    (-50, QColor(0, 200, 100)),
    (-65, QColor(150, 220, 50)),
    (-75, QColor(255, 200, 0)),
    (-85, QColor(255, 100, 0)),
    (-100, QColor(200, 0, 0)),
]


def dbm_to_color(dbm: float) -> QColor:
    if dbm >= SIGNAL_GRADIENT[0][0]:
        return SIGNAL_GRADIENT[0][1]
    if dbm <= SIGNAL_GRADIENT[-1][0]:
        return SIGNAL_GRADIENT[-1][1]

    for i in range(len(SIGNAL_GRADIENT) - 1):
        upper_dbm, upper_color = SIGNAL_GRADIENT[i]
        lower_dbm, lower_color = SIGNAL_GRADIENT[i + 1]
        if lower_dbm <= dbm <= upper_dbm:
            t = (dbm - lower_dbm) / (upper_dbm - lower_dbm)
            r = int(lower_color.red() + t * (upper_color.red() - lower_color.red()))
            g = int(lower_color.green() + t * (upper_color.green() - lower_color.green()))
            b = int(lower_color.blue() + t * (upper_color.blue() - lower_color.blue()))
            return QColor(r, g, b)

    return SIGNAL_GRADIENT[-1][1]


def dbm_to_percent(dbm: float) -> int:
    """Convert dBm (-100 … -50) to 0–100 %."""
    clamped = max(-100.0, min(-50.0, dbm))
    return int(2 * (clamped + 100))
