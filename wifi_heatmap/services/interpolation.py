from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from models.measurement import Measurement


def interpolate_measurements(
    measurements: list["Measurement"],
    width: int,
    height: int,
    method: str = "rbf",
) -> np.ndarray:
    """Interpolate sparse dBm measurements onto a (height x width) grid."""
    if len(measurements) < 3:
        return np.full((height, width), np.nan)

    xs = np.array([m.x for m in measurements])
    ys = np.array([m.y for m in measurements])
    values = np.array([m.dbm for m in measurements])

    grid_x, grid_y = np.meshgrid(np.arange(width), np.arange(height))
    points = np.column_stack([grid_x.ravel(), grid_y.ravel()])

    try:
        from scipy.interpolate import RBFInterpolator

        rbf = RBFInterpolator(
            np.column_stack([xs, ys]),
            values,
            smoothing=0.5,
            kernel="thin_plate_spline",
        )
        grid = rbf(points)
        return grid.reshape(height, width)
    except Exception:
        return np.full((height, width), np.nan)
