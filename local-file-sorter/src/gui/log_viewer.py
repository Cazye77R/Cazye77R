"""Session log viewer – color-coded JSON-Lines with AnimatedLogCanvas."""
from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from src.gui import theme
from src.gui.hud.widgets.animated_log import AnimatedLogCanvas

_REFRESH_MS = 1000


class LogViewer(ctk.CTkToplevel):
    def __init__(self, parent, log_path: Path | None = None) -> None:
        super().__init__(parent)
        self._log_path    = log_path
        self._last_size   = -1
        self._last_count  = 0
        self._closed      = False

        self.title("Log-Viewer")
        self.geometry("860x540")
        self.minsize(600, 360)
        self.configure(fg_color=theme.BG_DEEP)

        self._build()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=44, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, text="SESSION LOG", font=theme.FONT_MONO_BOLD,
                     text_color=theme.ACCENT_PRIMARY,
                     ).grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self._file_label = ctk.CTkLabel(hdr, text="—", font=theme.FONT_MONO_SM,
                                         text_color=theme.TEXT_MUTED)
        self._file_label.grid(row=0, column=1, padx=8, pady=12, sticky="w")

        ctk.CTkButton(hdr, text="Datei wählen", width=110,
                      command=self._choose_log,
                      **theme.btn_ghost()).grid(row=0, column=2, padx=16, pady=8, sticky="e")

        # AnimatedLogCanvas replaces the plain CTkTextbox
        self._log_canvas = AnimatedLogCanvas(self, bg=theme.SURFACE,
                                              highlightthickness=0, bd=0)
        self._log_canvas.grid(row=1, column=0, sticky="nsew")

        # Status bar
        self._status = ctk.CTkLabel(self, text="", font=theme.FONT_MONO_SM,
                                     text_color=theme.TEXT_MUTED, anchor="w",
                                     fg_color=theme.SURFACE)
        self._status.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))

    # ------------------------------------------------------------------

    def _choose_log(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Log-Datei wählen",
            filetypes=[("JSON-Lines", "*.jsonl"), ("Alle", "*")],
            initialdir=str(Path(__file__).parent.parent.parent / "logs"),
        )
        if path:
            self._log_path   = Path(path)
            self._last_size  = -1
            self._last_count = 0
            self._refresh()

    def _refresh(self) -> None:
        if self._closed:
            return
        if self._log_path and self._log_path.exists():
            size = self._log_path.stat().st_size
            if size != self._last_size:
                self._last_size = size
                self._reload()
        elif self._log_path:
            self._status.configure(text=f"Datei nicht gefunden: {self._log_path}")
        else:
            self._status.configure(text="Keine Log-Datei ausgewählt.")
        self.after(_REFRESH_MS, self._refresh)

    def _reload(self) -> None:
        entries: list[dict] = []
        try:
            with self._log_path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        entries.append(json.loads(raw))
                    except json.JSONDecodeError:
                        entries.append({"op_type": "raw", "source": raw,
                                        "destination": "", "timestamp": ""})
        except OSError as exc:
            self._status.configure(text=f"Lesefehler: {exc}")
            return

        new_count = len(entries)
        if new_count != self._last_count:
            # Full reload (simple: reload all, canvas handles display)
            self._log_canvas.load_entries(entries)
            self._last_count = new_count

        self._file_label.configure(text=self._log_path.name)
        self._status.configure(
            text=(f"{new_count} Einträge  ·  {self._last_size} Bytes  "
                  f"·  Auto-Refresh {_REFRESH_MS // 1000}s"),
            text_color=theme.TEXT_MUTED,
        )

    def _on_close(self) -> None:
        self._closed = True
        self.destroy()
