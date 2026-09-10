"""AnimatedLogCanvas – color-coded log display with slide-in rows."""
from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass, field

from src.gui import theme

ROW_H    = 22
PAD_X    = 8
PAD_Y    = 4
SLIDE_PX = 10          # start offset below final position
SLIDE_F  = 6           # frames to complete slide (~200 ms at 30fps)

_TS_W  = 195           # timestamp column width px
_OP_W  = 110           # op_type column width px

_COLORS = {
    "move_file":      theme.ACCENT_DIM,
    "move":           theme.ACCENT_DIM,
    "create_folder":  theme.ACCENT_PRIMARY,
    "error":          theme.ERROR,
    "success":        theme.SUCCESS,
}


@dataclass
class _Row:
    y_final: int
    y_now: float
    frame: int        # animation frames remaining
    ts_id:  int = 0
    op_id:  int = 0
    path_id: int = 0


class AnimatedLogCanvas(tk.Canvas):
    """Drop-in replacement for CTkTextbox in the log viewer."""

    def __init__(self, parent, **kw) -> None:
        super().__init__(parent, bg=theme.SURFACE, highlightthickness=0, bd=0, **kw)
        self._rows: list[_Row] = []
        self._animating = False
        self._scroll_offset = 0   # top-of-view y
        self.bind("<Configure>", self._on_resize)
        self._h = 400

    # ------------------------------------------------------------------
    def load_entries(self, entries: list[dict]) -> None:
        """Replace all rows (called on full reload from log file)."""
        self.delete("all")
        self._rows.clear()
        for entry in entries:
            self._append_row(entry, animate=False)
        self._scroll_to_end_instant()

    def add_entry(self, entry: dict) -> None:
        """Append one new entry with slide-in animation."""
        self._append_row(entry, animate=True)
        if not self._animating:
            self._animating = True
            self._animate_tick()

    # ------------------------------------------------------------------
    def _append_row(self, entry: dict, animate: bool) -> None:
        y_final = len(self._rows) * ROW_H + PAD_Y
        y_start = y_final + (SLIDE_PX if animate else 0)

        ts  = entry.get("timestamp", "")[:19].replace("T", " ")
        op  = entry.get("op_type", "?")
        src = entry.get("source") or ""
        dst = entry.get("destination") or ""
        path_txt = f"{src} → {dst}" if src else dst

        op_color   = _COLORS.get(op, theme.TEXT_MUTED)
        view_y     = y_start - self._scroll_offset

        ts_id   = self.create_text(PAD_X, view_y, anchor="nw",
                                   text=ts, fill=theme.ACCENT_PRIMARY,
                                   font=theme.FONT_MONO_SM)
        op_id   = self.create_text(PAD_X + _TS_W, view_y, anchor="nw",
                                   text=op, fill=op_color,
                                   font=theme.FONT_MONO_SM)
        path_id = self.create_text(PAD_X + _TS_W + _OP_W, view_y, anchor="nw",
                                   text=path_txt, fill=theme.TEXT_MUTED,
                                   font=theme.FONT_MONO_SM)

        row = _Row(y_final=y_final, y_now=y_start, frame=SLIDE_F if animate else 0,
                   ts_id=ts_id, op_id=op_id, path_id=path_id)
        self._rows.append(row)

        total_content = len(self._rows) * ROW_H + 2 * PAD_Y
        if total_content > self._h:
            self._scroll_offset = total_content - self._h
            self._reposition_all()

    def _animate_tick(self) -> None:
        if not self.winfo_exists():
            return
        still_animating = False
        for row in self._rows:
            if row.frame > 0:
                row.frame -= 1
                row.y_now += (row.y_final - row.y_now) * 0.55
                still_animating = True
                view_y = row.y_now - self._scroll_offset
                for item_id in (row.ts_id, row.op_id, row.path_id):
                    try:
                        coords = self.coords(item_id)
                        if coords:
                            self.coords(item_id, coords[0], view_y)
                    except Exception:
                        pass
        self._animating = still_animating
        if still_animating:
            self.after(33, self._animate_tick)

    def _reposition_all(self) -> None:
        for row in self._rows:
            view_y = row.y_now - self._scroll_offset
            for item_id in (row.ts_id, row.op_id, row.path_id):
                try:
                    coords = self.coords(item_id)
                    if coords:
                        self.coords(item_id, coords[0], view_y)
                except Exception:
                    pass

    def _scroll_to_end_instant(self) -> None:
        total = len(self._rows) * ROW_H + 2 * PAD_Y
        self._scroll_offset = max(0, total - self._h)
        self._reposition_all()

    def _on_resize(self, event) -> None:
        self._h = event.height
        self._scroll_to_end_instant()
