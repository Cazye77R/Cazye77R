"""Session log viewer – JSON-Lines formatted in a monospace panel."""
from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from src.gui import theme

_REFRESH_MS = 1000


class LogViewer(ctk.CTkToplevel):
    def __init__(self, parent, log_path: Path | None = None) -> None:
        super().__init__(parent)
        self._log_path  = log_path
        self._last_size = -1
        self._closed    = False

        self.title("Log-Viewer")
        self.geometry("820x520")
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

        # Text area
        self._text = ctk.CTkTextbox(
            self,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            font=theme.FONT_MONO_SM,
            corner_radius=0,
            wrap="none",
            state="disabled",
        )
        self._text.grid(row=1, column=0, sticky="nsew")

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
            self._log_path  = Path(path)
            self._last_size = -1
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
        lines = []
        try:
            with self._log_path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        parsed = json.loads(raw)
                        pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
                    except json.JSONDecodeError:
                        pretty = raw
                    lines.append(pretty)
                    lines.append("")
        except OSError as exc:
            lines = [f"Lesefehler: {exc}"]

        content = "\n".join(lines)

        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("end", content)
        self._text.configure(state="disabled")
        self._text.see("end")

        self._file_label.configure(text=self._log_path.name)
        n = len([l for l in lines if l.startswith("{")])
        self._status.configure(
            text=f"{n} Einträge  ·  {self._last_size} Bytes  ·  Auto-Refresh {_REFRESH_MS // 1000}s",
            text_color=theme.TEXT_MUTED,
        )

    def _on_close(self) -> None:
        self._closed = True
        self.destroy()
