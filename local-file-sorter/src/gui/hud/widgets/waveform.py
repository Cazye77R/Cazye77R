"""WaveformIndicator – 24 bars, sine-modulated, visible only during THINKING."""
from __future__ import annotations

import math
import random
import tkinter as tk

from src.gui import theme
from src.gui.hud.animation_engine import AnimState, AnimationEngine

N_BARS  = 24
W, H    = 400, 40
BAR_W   = W // N_BARS - 1
MAX_H   = H - 6
_BG     = (10, 14, 20)
_ACCENT = (0, 217, 255)
_DIM    = (76, 201, 240)


def _hex(t: tuple) -> str:
    return "#{:02x}{:02x}{:02x}".format(*t)


def _lerp_color(a: tuple, b: tuple, f: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


class WaveformIndicator(tk.Canvas):
    def __init__(self, parent, engine: AnimationEngine, **kw) -> None:
        super().__init__(parent, width=W, height=H,
                         bg=theme.BG_DEEP, highlightthickness=0, bd=0, **kw)
        self._engine  = engine
        self._state   = AnimState.IDLE
        self._t       = 0.0
        self._opacity = 0.0   # 0 = invisible, 1 = fully visible
        self._noise   = [random.uniform(-0.15, 0.15) for _ in range(N_BARS)]
        self._bar_ids = [self.create_rectangle(0, 0, 0, 0, fill=_hex(_DIM), outline="")
                         for _ in range(N_BARS)]
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
                self._t += 0.033
                self._update_opacity()
                if self._opacity > 0.01:
                    self._render()
        except Exception:
            pass
        self.after(33, self._tick)

    def _update_opacity(self) -> None:
        target = 1.0 if self._state == AnimState.THINKING else 0.0
        speed  = 0.08   # fade speed per frame
        if self._opacity < target:
            self._opacity = min(target, self._opacity + speed)
        elif self._opacity > target:
            self._opacity = max(target, self._opacity - speed)

    def _render(self) -> None:
        t = self._t
        op = self._opacity
        if self._engine.reduced_motion:
            # Static coloured bars – no animation
            heights = [MAX_H * 0.4] * N_BARS
        else:
            # Two sine waves + per-bar noise
            heights = []
            for i in range(N_BARS):
                phase = i / N_BARS * 2 * math.pi
                h = (
                    0.55 * math.sin(t * 2.8 + phase)
                    + 0.30 * math.sin(t * 5.1 + phase * 1.7)
                    + self._noise[i]
                )
                h = max(0.05, (h + 1.0) / 2.0)
                heights.append(h * MAX_H)

            # Slowly drift noise
            for i in range(N_BARS):
                self._noise[i] += random.uniform(-0.02, 0.02)
                self._noise[i] = max(-0.2, min(0.2, self._noise[i]))

        for i, bar_h in enumerate(heights):
            x0 = i * (BAR_W + 1)
            x1 = x0 + BAR_W
            y0 = H - int(bar_h)
            y1 = H

            # Colour: accent at tip, dim at base, modulated by opacity
            frac = bar_h / MAX_H
            color = _lerp_color(_BG, _lerp_color(_DIM, _ACCENT, frac), op)
            self.coords(self._bar_ids[i], x0, y0, x1, y1)
            self.itemconfig(self._bar_ids[i], fill=_hex(color))
