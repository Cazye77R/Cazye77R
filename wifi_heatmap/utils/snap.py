from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF

# Public type alias
SnapType = Optional[str]   # "point" | "edge" | "grid" | None


def snap_point(
    pos: QPointF,
    elements: list[dict],
    grid_size: int,
    snap_to_points: bool,
    snap_to_grid: bool,
    zoom: float = 1.0,
) -> tuple[QPointF, SnapType]:
    """
    Apply snap in priority order: point → edge → grid.

    Radii are given in screen pixels and converted to scene units via *zoom*.
    Returns (snapped_position, snap_type).  snap_type is None when no snap is
    active (caller should treat the raw position as-is).

    Priority
    --------
    1. Point snap  – element endpoints / rect corners,  radius 12 screen px
    2. Edge snap   – rect edges / line segments,        radius  8 screen px
    3. Grid snap   – nearest grid crossing,             always exact
    """
    if snap_to_points and elements:
        pt = _best_point_snap(pos, elements, 12.0 / zoom)
        if pt is not None:
            return pt, "point"

        ep = _best_edge_snap(pos, elements, 8.0 / zoom)
        if ep is not None:
            return ep, "edge"

    if snap_to_grid and grid_size > 0:
        gs = float(grid_size)
        return QPointF(round(pos.x() / gs) * gs, round(pos.y() / gs) * gs), "grid"

    return pos, None


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _best_point_snap(
    pos: QPointF, elements: list[dict], radius: float
) -> Optional[QPointF]:
    r2 = radius * radius
    best: Optional[QPointF] = None
    best_d2 = r2
    for elem in elements:
        for pt in _element_snap_points(elem):
            dx = pt.x() - pos.x()
            dy = pt.y() - pos.y()
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2, best = d2, pt
    return best


def _best_edge_snap(
    pos: QPointF, elements: list[dict], radius: float
) -> Optional[QPointF]:
    r2 = radius * radius
    best: Optional[QPointF] = None
    best_d2 = r2
    for elem in elements:
        for a, b in _element_edges(elem):
            pt = _closest_on_segment(pos, a, b)
            dx = pt.x() - pos.x()
            dy = pt.y() - pos.y()
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2, best = d2, pt
    return best


def _element_snap_points(elem: dict) -> list[QPointF]:
    """Corner / endpoint candidates for point-snap."""
    t = elem.get("type")
    if t == "rect":
        x, y, w, h = elem["x"], elem["y"], elem["w"], elem["h"]
        return [
            QPointF(x,     y    ),
            QPointF(x + w, y    ),
            QPointF(x,     y + h),
            QPointF(x + w, y + h),
        ]
    if t == "line":
        return [QPointF(elem["x1"], elem["y1"]),
                QPointF(elem["x2"], elem["y2"])]
    return []


def _element_edges(elem: dict) -> list[tuple[QPointF, QPointF]]:
    """All edges as (A, B) pairs for edge-snap."""
    t = elem.get("type")
    if t == "rect":
        x, y, w, h = elem["x"], elem["y"], elem["w"], elem["h"]
        tl = QPointF(x,     y    )
        tr = QPointF(x + w, y    )
        bl = QPointF(x,     y + h)
        br = QPointF(x + w, y + h)
        return [(tl, tr), (tr, br), (br, bl), (bl, tl)]
    if t == "line":
        return [(QPointF(elem["x1"], elem["y1"]),
                 QPointF(elem["x2"], elem["y2"]))]
    return []


def _closest_on_segment(p: QPointF, a: QPointF, b: QPointF) -> QPointF:
    """Orthogonal projection of *p* onto segment AB, clamped to [A, B]."""
    dx = b.x() - a.x()
    dy = b.y() - a.y()
    len2 = dx * dx + dy * dy
    if len2 < 1e-12:
        return QPointF(a)
    t = max(0.0, min(1.0,
            ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / len2))
    return QPointF(a.x() + t * dx, a.y() + t * dy)
