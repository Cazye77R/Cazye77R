"""CoreIndicator – concentric rotating rings with Pillow glow rendering."""
from __future__ import annotations

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from src.gui import theme
from src.gui.hud.animation_engine import AnimState, AnimationEngine

SIZE = 120
CX = CY = SIZE // 2
_BG = (10, 14, 20)      # theme.BG_DEEP as RGB
_SURFACE = (22, 27, 34) # theme.SURFACE as RGB

# Colour palettes per state (RGB triples)
_PALETTE = {
    AnimState.IDLE:      ((0, 217, 255),  (76, 201, 240)),   # accent, dim
    AnimState.SCANNING:  ((0, 217, 255),  (76, 201, 240)),
    AnimState.THINKING:  ((0, 217, 255),  (76, 201, 240)),
    AnimState.EXECUTING: ((0, 217, 255),  (76, 201, 240)),
    AnimState.SUCCESS:   ((0, 255, 157),  (0, 200, 120)),
    AnimState.ERROR:     ((255, 56, 96),  (200, 40, 70)),
}


def _blend(color: tuple, alpha: float, bg: tuple = _BG) -> tuple:
    return tuple(int(color[i] * alpha + bg[i] * (1.0 - alpha)) for i in range(3))


class CoreIndicator(tk.Canvas):
    def __init__(self, parent, engine: AnimationEngine, **kw) -> None:
        super().__init__(parent, width=SIZE, height=SIZE,
                         bg=theme.SURFACE, highlightthickness=0, bd=0, **kw)
        self._engine = engine
        self._state  = AnimState.IDLE
        self._t      = 0.0
        self._ang    = [0.0, 0.0, 0.0]   # angles for 3 rings
        self._sweep  = 0.0               # radar sweep angle (SCANNING)
        self._photo: ImageTk.PhotoImage | None = None
        self._bg_img = Image.new("RGBA", (SIZE, SIZE), (*_SURFACE, 255))
        self._img_id = self.create_image(0, 0, anchor="nw")
        engine.register(self)
        self._tick()

    def on_state_change(self, state: AnimState) -> None:
        self._state = state

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        try:
            if self._engine.enabled and self.winfo_ismapped():
                self._update(0.033)
                self._render()
        except Exception:
            pass
        self.after(33, self._tick)

    def _update(self, dt: float) -> None:
        self._t += dt
        s = self._state
        rm = self._engine.reduced_motion
        if rm or s == AnimState.ERROR:
            return
        if s == AnimState.IDLE:
            speeds = (22, -28, 40)          # deg/s per ring
        elif s == AnimState.SCANNING:
            speeds = (45, -55, 72)
            self._sweep = (self._sweep + 180 * dt) % 360
        elif s == AnimState.THINKING:
            speeds = (100, -130, 165)
        elif s == AnimState.EXECUTING:
            speeds = (70, -90, 115)
        else:
            speeds = (15, -20, 28)
        for i, spd in enumerate(speeds):
            self._ang[i] = (self._ang[i] + spd * dt) % 360

    # ------------------------------------------------------------------
    def _render(self) -> None:
        img = self._bg_img.copy()
        draw = ImageDraw.Draw(img)
        s = self._state
        t = self._t
        rm = self._engine.reduced_motion
        accent, dim = _PALETTE.get(s, _PALETTE[AnimState.IDLE])

        if rm:
            self._draw_reduced(draw, accent, dim)
        elif s == AnimState.EXECUTING:
            self._draw_segments(draw, accent, dim)
        else:
            self._draw_rings(draw, s, accent, dim)

        if s == AnimState.SCANNING and not rm:
            sw = self._sweep
            self._arc(draw, 54, _blend(accent, 1.0), sw, 8, 4)

        # Core
        pulse = 0.65 + 0.35 * math.sin(t * (8.0 if s == AnimState.ERROR else 3.14))
        self._draw_core(img, draw, accent, pulse, s, rm)

        if s == AnimState.ERROR and not rm and int(t * 10) % 7 == 0:
            gy = CY + int(math.sin(t * 50) * 15)
            draw.line([CX - 44, gy, CX + 44, gy], fill=_blend(accent, 0.4), width=1)

        self._photo = ImageTk.PhotoImage(img.convert("RGB"))
        self.itemconfig(self._img_id, image=self._photo)

    # ------------------------------------------------------------------
    def _draw_reduced(self, draw, accent, dim) -> None:
        for r, c in [(50, dim), (38, dim), (26, dim)]:
            self._arc(draw, r, _blend(c, 0.5), 0, 359, 2)

    def _draw_rings(self, draw, state, accent, dim) -> None:
        arc_len = 200 if state == AnimState.THINKING else 260
        for r, c, a in [(50, accent, 0), (38, dim, 1), (26, accent, 2)]:
            self._arc(draw, r, _blend(c, 0.18), 0, 359, 2)   # track (faint)
            ang = self._ang[a]
            self._arc(draw, r, _blend(c, 0.9), ang, arc_len, 2)
            # Leading bright tip
            self._arc(draw, r, _blend(accent, 1.0), ang + arc_len - 12, 12, 3)

    def _draw_segments(self, draw, accent, dim) -> None:
        n, seg = 6, 25
        for idx in range(n):
            for r, c, ai in [(50, accent, 0), (38, dim, 1), (26, accent, 2)]:
                a = (self._ang[ai] + idx * (360 // n)) % 360
                self._arc(draw, r, _blend(c, 0.85 if idx % 2 == 0 else 0.5), a, seg, 2)

    def _draw_core(self, img, draw, accent, pulse, state, rm) -> None:
        r = 11
        gr = int(14 + 4 * pulse)
        if not rm and state == AnimState.THINKING:
            self._glow(img, CX, CY, r + 10, accent, alpha=70)
        self._glow(img, CX, CY, gr, accent, alpha=int(55 * pulse))
        a = int(255 * pulse)
        fill = tuple(min(255, int(accent[i] * pulse)) for i in range(3))
        draw.ellipse([CX - r, CY - r, CX + r, CY + r], fill=(*fill, 255))

    # ------------------------------------------------------------------
    @staticmethod
    def _arc(draw, r, color, start, length, width) -> None:
        bbox = [CX - r, CY - r, CX + r, CY + r]
        s = start % 360
        e = (s + length) % 360
        if len(color) == 3:
            color = (*color, 255)
        if e > s:
            draw.arc(bbox, s, e, fill=color, width=width)
        else:
            draw.arc(bbox, s, 359, fill=color, width=width)
            if e > 0:
                draw.arc(bbox, 0, e, fill=color, width=width)

    @staticmethod
    def _glow(img, cx, cy, r, color, alpha=60) -> None:
        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=5)))
