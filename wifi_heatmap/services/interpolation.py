from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QImage


class HeatmapGenerator:
    """Generate WiFi signal heatmaps from a list of measurement points."""

    def generate(
        self,
        measurements: list[Any],   # objects with .x  .y  .dbm  (local coords)
        width: int,
        height: int,
        resolution: int = 5,
    ) -> np.ndarray:
        """Interpolate dBm over a 2-D grid of shape (h//res+1, w//res+1).

        Returns float64 array; cells far from any measurement contain NaN.
        Falls back to nearest-neighbour when fewer than 3 points are given.
        """
        from scipy.interpolate import NearestNDInterpolator, RBFInterpolator
        from scipy.spatial.distance import cdist

        # Build the sample grid in local coords
        gx = np.arange(0, width  + resolution, resolution, dtype=float)
        gy = np.arange(0, height + resolution, resolution, dtype=float)
        GX, GY = np.meshgrid(gx, gy)
        grid_pts = np.column_stack([GX.ravel(), GY.ravel()])

        if not measurements:
            return np.full(GX.shape, np.nan)

        pts  = np.array([[m.x, m.y] for m in measurements], dtype=float)
        dbms = np.array([m.dbm      for m in measurements], dtype=float)

        # ── Interpolation ─────────────────────────────────────────────────────
        if len(measurements) < 3:
            # Nearest-neighbour — always well-behaved
            interp = NearestNDInterpolator(pts, dbms)
            values = interp(grid_pts)
        else:
            interp = RBFInterpolator(
                pts, dbms,
                kernel="thin_plate_spline",
                smoothing=1e-3,   # near-exact interpolation, damps oscillations
            )
            values = interp(grid_pts)

        # ── Boundary decay — prevent wild extrapolation ────────────────────────
        # Distance from every grid cell to the nearest measurement
        dists = cdist(grid_pts, pts).min(axis=1)

        # Characteristic spacing between measurements
        if len(pts) >= 2:
            pw = cdist(pts, pts)
            np.fill_diagonal(pw, np.inf)
            char_scale = float(np.median(pw.min(axis=1)))
        else:
            char_scale = float(max(width, height)) * 0.5

        # Gaussian falloff; cells with decay < 5 % become NaN (transparent)
        decay_scale = max(char_scale * 2.0, min(width, height) * 0.15)
        decay = np.exp(-0.5 * (dists / decay_scale) ** 2)

        # Clamp to a sane dBm range, then blend toward measured minimum at edges
        lo = float(dbms.min()) - 15.0
        hi = float(dbms.max()) +  5.0
        values_clamped = np.clip(values, lo, hi)
        values_blended = decay * values_clamped + (1.0 - decay) * float(dbms.min())
        values_blended[decay < 0.05] = np.nan

        return values_blended.reshape(GX.shape)

    def generate_image(
        self,
        dbm_grid: np.ndarray,
        min_dbm: float = -90.0,
        max_dbm: float = -30.0,
        opacity: float = 0.5,
        target_width:  int | None = None,
        target_height: int | None = None,
    ) -> QImage:
        """Convert *dbm_grid* to an RGBA QImage using the R→Y→G gradient.

        NaN cells are fully transparent.  Non-NaN cells use *opacity* (0–1).
        If *target_width* / *target_height* are given, the grid is bilinearly
        upsampled to that resolution before colourisation.
        """
        from scipy.ndimage import zoom as ndimage_zoom

        h, w = dbm_grid.shape

        # ── Optional bilinear upsampling ──────────────────────────────────────
        if target_width is not None and target_height is not None:
            zy = target_height / h
            zx = target_width  / w
            if abs(zy - 1.0) > 0.01 or abs(zx - 1.0) > 0.01:
                nan_mask = np.isnan(dbm_grid)
                filled   = np.where(nan_mask, 0.0, dbm_grid)
                weight   = (~nan_mask).astype(float)
                f_up     = ndimage_zoom(filled, (zy, zx), order=1)
                w_up     = ndimage_zoom(weight, (zy, zx), order=1)
                valid_up = w_up > 0.1
                result   = np.full(f_up.shape, np.nan)
                # Weighted blend avoids NaN bleed-in at the coverage boundary
                result[valid_up] = f_up[valid_up] / w_up[valid_up]
                dbm_grid = result
                h, w     = dbm_grid.shape

        # ── Colour mapping (R → Y → G) ────────────────────────────────────────
        rgba  = np.zeros((h, w, 4), dtype=np.uint8)
        valid = ~np.isnan(dbm_grid)

        if valid.any():
            t = np.clip(
                (dbm_grid[valid] - min_dbm) / (max_dbm - min_dbm),
                0.0, 1.0,
            )
            half = t <= 0.5

            r = np.empty(t.shape, dtype=np.uint8)
            g = np.empty(t.shape, dtype=np.uint8)

            r[half]  = 255
            r[~half] = np.clip(
                ((1.0 - (t[~half] - 0.5) / 0.5) * 255), 0, 255
            ).astype(np.uint8)
            g[half]  = np.clip((t[half] / 0.5 * 255), 0, 255).astype(np.uint8)
            g[~half] = 255

            a = int(np.clip(opacity, 0.0, 1.0) * 255)
            rgba[valid, 0] = r
            rgba[valid, 1] = g
            rgba[valid, 2] = 0
            rgba[valid, 3] = a

        data = rgba.tobytes()
        img  = QImage(data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
        return img.copy()   # detach from numpy buffer before it may be freed


# ── Legacy function kept for backward compatibility ───────────────────────────

def interpolate_measurements(
    measurements,
    width: int,
    height: int,
    method: str = "rbf",
) -> np.ndarray:
    """Thin wrapper around HeatmapGenerator.generate() at full resolution."""
    return HeatmapGenerator().generate(measurements, width, height, resolution=1)
