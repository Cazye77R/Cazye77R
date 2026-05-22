"""BootSequence – one-shot intro overlay: sweep line + type-on text."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

from src.gui import theme

_LINES = [
    "> SYSTEM ONLINE",
    "> MODEL: QWEN2.5-7B Q4",
    "> READY",
]
_CHAR_DELAY  = 28    # ms per character
_LINE_GAP    = 340   # ms between lines starting
_HOLD_AFTER  = 500   # ms hold before dismiss
_SWEEP_MS    = 320   # ms for sweep line

_BG    = (10, 14, 20)
_CYAN  = (0, 217, 255)
_DIM   = (76, 201, 240)


class BootSequence(tk.Canvas):
    """
    Full-window Canvas overlay placed over the SorterApp.
    Call .start() once the parent window is mapped.
    """

    def __init__(self, parent: tk.Widget, on_done: Callable[[], None]) -> None:
        super().__init__(parent, bg=theme.BG_DEEP, highlightthickness=0, bd=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)  # widget-level raise; Canvas.lift is tag_raise (item-level)

        self._parent  = parent
        self._on_done = on_done
        self._done    = False
        self._photo: ImageTk.PhotoImage | None = None
        self._img_id: int | None = None
        self._sweep_x = 0

        # Bind skip keys
        parent.bind("<Escape>", lambda _: self._finish(), add="+")
        self.bind("<Button-1>", lambda _: self._finish())

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._width = self.winfo_width()
        self._height = self.winfo_height()
        if self._width < 10:  # not yet mapped
            self.after(50, self.start)
            return
        self._render_bg()
        self._run_sweep(0)

    # ------------------------------------------------------------------
    # Sweep phase
    # ------------------------------------------------------------------

    def _run_sweep(self, step: int) -> None:
        if self._done:
            return
        total_steps = _SWEEP_MS // 16
        x = int(self._width * step / total_steps)
        self._draw_sweep(x)
        if step < total_steps:
            self.after(16, lambda: self._run_sweep(step + 1))
        else:
            self._draw_sweep(self._width)
            self.after(80, self._start_typing)

    def _draw_sweep(self, x: int) -> None:
        if self._done:
            return
        w, h = self._width, self._height
        img = Image.new("RGBA", (w, h), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Faint scan lines
        for y in range(0, h, 4):
            draw.line([(0, y), (w, y)], fill=(20, 30, 40, 255), width=1)

        # Sweep glow
        for gx in range(max(0, x - 30), min(w, x + 4)):
            alpha = int(180 * (1 - abs(gx - x) / 30))
            draw.line([(gx, 0), (gx, h)], fill=(*_CYAN, alpha), width=1)

        # Hard leading edge
        if x < w:
            draw.line([(x, 0), (x, h)], fill=(*_CYAN, 255), width=2)

        self._photo = ImageTk.PhotoImage(img.convert("RGB"))
        if self._img_id is None:
            self._img_id = self.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.itemconfig(self._img_id, image=self._photo)

    # ------------------------------------------------------------------
    # Type-on phase
    # ------------------------------------------------------------------

    def _start_typing(self) -> None:
        if self._done:
            return
        self._typed: list[str] = []
        self._type_line(0, 0)

    def _type_line(self, line_idx: int, char_idx: int) -> None:
        if self._done:
            return
        if line_idx >= len(_LINES):
            self.after(_HOLD_AFTER, self._finish)
            return

        full = _LINES[line_idx]
        if char_idx <= len(full):
            partial = full[:char_idx]
            self._typed_current = (line_idx, partial)
            self._draw_text(line_idx, partial)
            self.after(_CHAR_DELAY,
                       lambda: self._type_line(line_idx, char_idx + 1))
        else:
            if line_idx + 1 < len(_LINES):
                self.after(_LINE_GAP - len(full) * _CHAR_DELAY,
                           lambda: self._type_line(line_idx + 1, 0))
            else:
                self.after(_HOLD_AFTER, self._finish)

    def _draw_text(self, current_line: int, partial: str) -> None:
        if self._done:
            return
        w, h = self._width, self._height
        img = Image.new("RGBA", (w, h), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Scan lines
        for y in range(0, h, 4):
            draw.line([(0, y), (w, y)], fill=(20, 30, 40, 255), width=1)

        # Corner decoration
        self._draw_corners(draw, w, h)

        # Completed lines
        mono = theme.FONT_MONO
        fam  = mono[0] if mono else "Courier New"
        size = 16
        try:
            from PIL import ImageFont
            font = ImageFont.truetype(fam + ".ttf", size)
        except Exception:
            font = None

        base_y = h // 2 - 40
        for i, line in enumerate(_LINES[:current_line]):
            color = _DIM if i < current_line - 1 else _CYAN
            self._draw_string(draw, 60, base_y + i * 36, line, _DIM, font)

        # Current partial line with cursor
        self._draw_string(draw, 60, base_y + current_line * 36, partial + "█", _CYAN, font)

        self._photo = ImageTk.PhotoImage(img.convert("RGB"))
        if self._img_id is None:
            self._img_id = self.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.itemconfig(self._img_id, image=self._photo)

    @staticmethod
    def _draw_string(draw, x, y, text, color, font) -> None:
        if font:
            draw.text((x, y), text, fill=(*color, 255), font=font)
        else:
            draw.text((x, y), text, fill=(*color, 255))

    @staticmethod
    def _draw_corners(draw, w, h) -> None:
        c, L = (*_CYAN, 120), 20
        draw.line([(2, 2), (L, 2)],      fill=c, width=1)
        draw.line([(2, 2), (2, L)],      fill=c, width=1)
        draw.line([(w - L, 2), (w - 2, 2)], fill=c, width=1)
        draw.line([(w - 2, 2), (w - 2, L)], fill=c, width=1)
        draw.line([(2, h - L), (2, h - 2)], fill=c, width=1)
        draw.line([(2, h - 2), (L, h - 2)], fill=c, width=1)
        draw.line([(w - 2, h - L), (w - 2, h - 2)], fill=c, width=1)
        draw.line([(w - L, h - 2), (w - 2, h - 2)], fill=c, width=1)

    def _render_bg(self) -> None:
        pass  # drawn fresh each frame

    # ------------------------------------------------------------------
    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        try:
            self._parent.unbind("<Escape>")
        except Exception:
            pass
        self.place_forget()
        self.destroy()
        try:
            self._on_done()
        except Exception:
            pass
