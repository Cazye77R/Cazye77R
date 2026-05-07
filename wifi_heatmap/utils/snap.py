from __future__ import annotations


def snap_to_grid(x: float, y: float, grid_size: int) -> tuple[float, float]:
    snapped_x = round(x / grid_size) * grid_size
    snapped_y = round(y / grid_size) * grid_size
    return float(snapped_x), float(snapped_y)
