"""ActivityStream – particles fly left→right on every completed move action."""
from __future__ import annotations

import math
import queue
import random
import tkinter as tk
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageTk

from src.gui import theme
from src.gui.hud.animation_engine import AnimState, AnimationEngine

W, H       = 600, 60
MAX_P      = 15        # max simultaneous particles
TRAIL_LEN  = 10        # trail history length
_BG        = (10, 14, 20)
_ACCENT    = (0, 217, 255)
_ERROR_C   = (255, 56, 96)
_BG_IMG    = None      # lazy init


@dataclass
class _Particle:
    x: float
    y: float
    speed: float
    radius: int
    color: tuple
    trail: list = field(default_factory=list)

    def step(self) -> None:
        self.trail.append((self.x, self.y))
        if len(self.trail) > TRAIL_LEN:
            self.trail.pop(0)
        self.x += self.speed

    @property
    def alive(self) -> bool:
        return self.x < W + 20


class ActivityStream(tk.Canvas):
    def __init__(self, parent, engine: AnimationEngine, **kw) -> None:
        super().__init__(parent, width=W, height=H,
                         bg=theme.BG_DEEP, highlightthickness=0, bd=0, **kw)
        self._engine  = engine
        self._state   = AnimState.IDLE
        self._parts: list[_Particle] = []
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._photo: ImageTk.PhotoImage | None = None
        self._img_id  = self.create_image(0, 0, anchor="nw")
        self._bg_img  = Image.new("RGBA", (W, H), (*_BG, 255))
        engine.register(self)
        engine.subscribe_events(self._on_event)
        self._tick()

    def on_state_change(self, state: AnimState) -> None:
        self._state = state

    def spawn(self, success: bool = True) -> None:
        """Thread-safe: call from any thread after a move completes."""
        self._queue.put(success)

    # ------------------------------------------------------------------
    def _on_event(self, event_type: str, data) -> None:
        if event_type == "move":
            self.spawn(success=bool(data))

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        try:
            if self._engine.enabled and self.winfo_ismapped():
                self._drain_queue()
                self._step_particles()
                self._render()
        except Exception:
            pass
        self.after(33, self._tick)

    def _drain_queue(self) -> None:
        while not self._queue.empty() and len(self._parts) < MAX_P:
            try:
                ok = self._queue.get_nowait()
                self._add_particle(ok)
            except queue.Empty:
                break

    def _add_particle(self, success: bool) -> None:
        if self._engine.reduced_motion:
            return
        color = _ACCENT if (success and self._state != AnimState.ERROR) else _ERROR_C
        self._parts.append(_Particle(
            x=-5.0,
            y=random.uniform(H * 0.2, H * 0.8),
            speed=random.uniform(3.0, 6.5),
            radius=random.randint(3, 5),
            color=color,
        ))

    def _step_particles(self) -> None:
        for p in self._parts:
            p.step()
        self._parts = [p for p in self._parts if p.alive]

    def _render(self) -> None:
        img = self._bg_img.copy()
        draw = ImageDraw.Draw(img)

        # Subtle grid lines
        for x in range(0, W, 60):
            r, g, b = _BG
            line_c = (r + 8, g + 10, b + 12)
            draw.line([(x, 0), (x, H)], fill=(*line_c, 255), width=1)
        for y in [H // 3, H * 2 // 3]:
            draw.line([(0, y), (W, y)], fill=(20, 27, 36, 255), width=1)

        if self._engine.reduced_motion:
            self._photo = ImageTk.PhotoImage(img.convert("RGB"))
            self.itemconfig(self._img_id, image=self._photo)
            return

        # Render each particle + trail
        for p in self._parts:
            # Trail
            for ti, (tx, ty) in enumerate(p.trail):
                frac  = (ti + 1) / len(p.trail) if p.trail else 1.0
                alpha = int(200 * frac)
                tr    = max(1, p.radius - 2)
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ld    = ImageDraw.Draw(layer)
                ld.ellipse([tx - tr, ty - tr, tx + tr, ty + tr],
                           fill=(*p.color, alpha))
                img.alpha_composite(layer)

            # Head
            r = p.radius
            draw.ellipse([p.x - r, p.y - r, p.x + r, p.y + r],
                         fill=(*p.color, 255))
            # Tiny bright core
            if r > 3:
                draw.ellipse([p.x - 1, p.y - 1, p.x + 1, p.y + 1],
                             fill=(255, 255, 255, 220))

        self._photo = ImageTk.PhotoImage(img.convert("RGB"))
        self.itemconfig(self._img_id, image=self._photo)
