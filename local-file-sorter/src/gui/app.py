"""Main application window – HUD cockpit aesthetic."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import yaml

from src.core.logger import OperationLogger
from src.core.mover import move_file, create_folder
from src.core.scanner import scan_folder
from src.core.undo import undo_session
from src.gui import theme
from src.llm.ollama_client import OllamaClient, PlanValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
_LOG_DIR       = Path(__file__).parent.parent.parent / "logs"
_WINDOW_SIZE   = "960x720"
_WINDOW_TITLE  = "LOCAL-FILE-SORTER  //  HUD v0.1"


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    with _SETTINGS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _save_settings(cfg: dict) -> None:
    with _SETTINGS_PATH.open("w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh, allow_unicode=True, default_flow_style=False)


# ---------------------------------------------------------------------------
# OS helper
# ---------------------------------------------------------------------------

def _open_in_explorer(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import os
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


# ---------------------------------------------------------------------------
# Settings Dialog
# ---------------------------------------------------------------------------

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent: "SorterApp", cfg: dict) -> None:
        super().__init__(parent)
        self._parent = parent
        self._cfg    = cfg

        self.title("Einstellungen")
        self.geometry("480x340")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self.focus_set()

        self._build()

    def _build(self) -> None:
        pad = {"padx": 24, "pady": 10}

        ctk.CTkLabel(self, text="EINSTELLUNGEN", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", **pad)

        self._add_row("Ollama URL",   self._cfg["ollama"]["base_url"],  "_url")
        self._add_row("Modell",       self._cfg["ollama"]["model"],     "_model")

        # Dry-run toggle
        dry_frame = ctk.CTkFrame(self, fg_color="transparent")
        dry_frame.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(dry_frame, text="Dry-Run (kein echtes Verschieben)",
                     text_color=theme.TEXT, font=theme.FONT_BODY).pack(side="left")
        self._dry_var = ctk.BooleanVar(value=self._cfg["app"]["dry_run"])
        ctk.CTkCheckBox(dry_frame, text="", variable=self._dry_var,
                        fg_color=theme.ACCENT_PRIMARY,
                        checkmark_color=theme.BG_DEEP).pack(side="right")

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkButton(btn_row, text="Speichern", width=120,
                      command=self._save, **theme.btn_primary()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Abbrechen", width=120,
                      command=self.destroy, **theme.btn_ghost()).pack(side="right")

    def _add_row(self, label: str, default: str, attr: str) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(row, text=label, width=120, anchor="w",
                     text_color=theme.TEXT_MUTED, font=theme.FONT_BODY).pack(side="left")
        var = ctk.StringVar(value=default)
        setattr(self, attr, var)
        ctk.CTkEntry(row, textvariable=var, fg_color=theme.SURFACE,
                     border_color=theme.SURFACE_HI, text_color=theme.TEXT,
                     font=theme.FONT_MONO_SM).pack(side="left", fill="x", expand=True)

    def _save(self) -> None:
        self._cfg["ollama"]["base_url"] = self._url.get().strip()
        self._cfg["ollama"]["model"]    = self._model.get().strip()
        self._cfg["app"]["dry_run"]     = self._dry_var.get()
        _save_settings(self._cfg)
        self._parent.reload_settings()
        self.destroy()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class SorterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Patch mono fonts after Tk is alive
        theme.apply_mono_family(theme.resolve_mono_family())

        self.title(_WINDOW_TITLE)
        self.geometry(_WINDOW_SIZE)
        self.minsize(800, 600)
        self.configure(fg_color=theme.BG_DEEP)

        self._cfg: dict = _load_settings()
        self._folder: Path | None = None
        self._last_log_path: Path | None = self._find_latest_log()
        self._busy = False

        self._build_ui()
        self._set_status("Bereit", color=theme.TEXT_MUTED)

        # Prevent accidental Enter-key execution
        self.bind_all("<Return>", lambda e: "break" if self._busy else None)
        self.bind_all("<KP_Enter>", lambda e: "break" if self._busy else None)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_folder_section()
        self._build_command_section()
        self._build_action_row()
        self._build_status_bar()

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=52, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, text="⚡  LOCAL-FILE-SORTER",
                     font=theme.FONT_TITLE, text_color=theme.ACCENT_PRIMARY
                     ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        ctk.CTkLabel(hdr, text="Qwen2.5 7B · Ollama",
                     font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED
                     ).grid(row=0, column=1, sticky="w", padx=6)

        ctk.CTkButton(hdr, text="⚙", width=40, height=32,
                      command=self._open_settings,
                      **theme.btn_ghost()
                      ).grid(row=0, column=2, padx=16, pady=10, sticky="e")

    def _build_folder_section(self) -> None:
        card = ctk.CTkFrame(self, **theme.card())
        card.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 4))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="ZIELVERZEICHNIS", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).grid(row=0, column=0, columnspan=3,
                                                        sticky="w", padx=16, pady=(12, 4))

        ctk.CTkButton(card, text="📁  Ordner wählen", width=160,
                      command=self._choose_folder,
                      **theme.btn_ghost()
                      ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        self._path_label = ctk.CTkLabel(card, text="— kein Ordner gewählt —",
                                         font=theme.FONT_MONO_SM,
                                         text_color=theme.TEXT_MUTED,
                                         anchor="w")
        self._path_label.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="ew")

        self._recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(card, text="Unterordner einbeziehen",
                        variable=self._recursive_var,
                        font=theme.FONT_BODY_SM,
                        text_color=theme.TEXT,
                        fg_color=theme.ACCENT_PRIMARY,
                        checkmark_color=theme.BG_DEEP,
                        hover_color=theme.ACCENT_DIM,
                        ).grid(row=1, column=2, padx=16, pady=(0, 12), sticky="e")

    def _build_command_section(self) -> None:
        card = ctk.CTkFrame(self, **theme.card())
        card.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(card, text="SORTIERBEFEHL", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).grid(row=0, column=0,
                                                         sticky="w", padx=16, pady=(12, 4))

        # Saved commands dropdown (populated in Phase 5)
        self._saved_cmd_var = ctk.StringVar(value="— Gespeicherte Befehle —")
        self._cmd_menu = ctk.CTkOptionMenu(
            card,
            variable=self._saved_cmd_var,
            values=["— Gespeicherte Befehle —"],
            command=self._on_saved_command,
            fg_color=theme.SURFACE_HI,
            button_color=theme.SURFACE_HI,
            button_hover_color="#2d3748",
            text_color=theme.TEXT_MUTED,
            dropdown_fg_color=theme.SURFACE,
            dropdown_hover_color=theme.SURFACE_HI,
            dropdown_text_color=theme.TEXT,
            font=theme.FONT_BODY_SM,
            width=260,
        )
        self._cmd_menu.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self._cmd_box = ctk.CTkTextbox(
            card,
            height=110,
            fg_color=theme.SURFACE_HI,
            border_color=theme.SURFACE_HI,
            border_width=1,
            text_color=theme.TEXT,
            font=theme.FONT_MONO,
            corner_radius=6,
            wrap="word",
        )
        self._cmd_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self._cmd_box.insert("end", "Sortiere nach Dateiendung in Unterordner")

        # Prevent Enter from submitting
        self._cmd_box.bind("<Return>", lambda e: None)

    def _build_action_row(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=3, column=0, sticky="ew", padx=16, pady=8)

        self._plan_btn = ctk.CTkButton(row, text="▶  PLAN GENERIEREN", width=200,
                                        command=self._on_generate_plan,
                                        **theme.btn_primary())
        self._plan_btn.pack(side="left", padx=(0, 10))

        self._undo_btn = ctk.CTkButton(row, text="↩  Undo letzte Session", width=190,
                                        command=self._on_undo,
                                        **theme.btn_ghost())
        self._undo_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(row, text="📋  Logs öffnen", width=140,
                      command=lambda: _open_in_explorer(_LOG_DIR),
                      **theme.btn_ghost()).pack(side="left")

        ctk.CTkButton(row, text="📄  Log-Viewer", width=140,
                      command=self._open_log_viewer,
                      **theme.btn_ghost()).pack(side="left", padx=(10, 0))

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=34, corner_radius=0)
        bar.grid(row=4, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(bar, text="●", font=("", 10),
                                         text_color=theme.TEXT_MUTED)
        self._status_dot.grid(row=0, column=0, padx=(14, 4), pady=8)

        self._status_label = ctk.CTkLabel(bar, text="", font=theme.FONT_MONO_SM,
                                           text_color=theme.TEXT_MUTED, anchor="w")
        self._status_label.grid(row=0, column=1, sticky="w", pady=8)

        self._progress = ctk.CTkProgressBar(bar, height=4,
                                             fg_color=theme.SURFACE_HI,
                                             progress_color=theme.ACCENT_PRIMARY,
                                             corner_radius=0)
        self._progress.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._progress.set(0)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, color: str = theme.TEXT_MUTED,
                    progress: float | None = None) -> None:
        self._status_label.configure(text=msg, text_color=color)
        self._status_dot.configure(text_color=color)
        if progress is not None:
            self._progress.set(progress)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self._plan_btn.configure(state=state)
        self._undo_btn.configure(state=state)

    def reload_settings(self) -> None:
        self._cfg = _load_settings()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Zielverzeichnis wählen")
        if folder:
            self._folder = Path(folder)
            self._path_label.configure(text=str(self._folder),
                                        text_color=theme.TEXT)

    def _on_saved_command(self, choice: str) -> None:
        if not choice.startswith("—"):
            self._cmd_box.delete("1.0", "end")
            self._cmd_box.insert("end", choice)

    def _open_settings(self) -> None:
        SettingsDialog(self, self._cfg)

    def _open_log_viewer(self) -> None:
        from src.gui.log_viewer import LogViewer
        LogViewer(self, log_path=self._last_log_path)

    # ------------------------------------------------------------------
    # Plan generation (threaded)
    # ------------------------------------------------------------------

    def _on_generate_plan(self) -> None:
        if self._folder is None:
            self._set_status("⚠  Kein Ordner gewählt.", color=theme.WARNING)
            return
        if not self._folder.is_dir():
            self._set_status("⚠  Pfad existiert nicht.", color=theme.WARNING)
            return

        command = self._cmd_box.get("1.0", "end").strip()
        if not command:
            self._set_status("⚠  Befehl ist leer.", color=theme.WARNING)
            return

        self._set_busy(True)
        self._set_status("Scanne Verzeichnis …", color=theme.ACCENT_PRIMARY, progress=0.15)

        threading.Thread(
            target=self._generate_plan_worker,
            args=(command,),
            daemon=True,
        ).start()

    def _generate_plan_worker(self, command: str) -> None:
        try:
            recursive = self._recursive_var.get()
            files = scan_folder(self._folder, recursive=recursive)
            files = [f for f in files if not f.is_dir]

            if not files:
                self.after(0, lambda: self._set_status(
                    "⚠  Keine Dateien im Verzeichnis.", color=theme.WARNING))
                self.after(0, lambda: self._set_busy(False))
                return

            self.after(0, lambda: self._set_status(
                f"Frage Modell … ({len(files)} Dateien)", color=theme.ACCENT_PRIMARY, progress=0.45))

            client = OllamaClient(
                model=self._cfg["ollama"]["model"],
                base_url=self._cfg["ollama"]["base_url"],
            )
            plan = client.generate_plan(
                files=files,
                user_command=command,
                target_folder=self._folder,
            )

            self.after(0, lambda: self._on_plan_ready(plan))

        except PlanValidationError as exc:
            msg = str(exc)
            self.after(0, lambda: self._set_status(
                f"⚠  Plan ungültig: {msg[:80]}", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))
        except Exception as exc:
            msg = str(exc)
            if "refused" in msg.lower() or "connect" in msg.lower():
                human = "Modell nicht erreichbar – läuft Ollama?"
            else:
                human = f"Fehler: {msg[:100]}"
            self.after(0, lambda: self._set_status(f"✗  {human}", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))

    def _on_plan_ready(self, plan) -> None:
        from src.gui.preview_dialog import PreviewDialog
        self._set_status("Plan empfangen – Vorschau …", color=theme.SUCCESS, progress=0.9)
        dlg = PreviewDialog(
            parent=self,
            plan=plan,
            target_folder=self._folder,
            log_dir=_LOG_DIR,
            dry_run=self._cfg["app"]["dry_run"],
            on_complete=self._on_execution_complete,
        )
        dlg.grab_set()
        self._set_busy(False)

    # ------------------------------------------------------------------
    # Execution completion callback
    # ------------------------------------------------------------------

    def _on_execution_complete(self, ok: int, fail: int, log_path: Path) -> None:
        self._last_log_path = log_path
        color = theme.SUCCESS if fail == 0 else theme.WARNING
        self._set_status(
            f"✓ Fertig – {ok} erfolgreich, {fail} fehlgeschlagen.  Log: {log_path.name}",
            color=color,
            progress=1.0,
        )

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        log_path = self._last_log_path
        if log_path is None or not log_path.exists():
            self._set_status("⚠  Kein Session-Log gefunden.", color=theme.WARNING)
            return

        self._set_busy(True)
        self._set_status("Mache letzte Session rückgängig …", color=theme.ACCENT_PRIMARY, progress=0.2)

        def _worker():
            try:
                results = undo_session(log_path)
                ok   = sum(1 for r in results if r.success)
                fail = sum(1 for r in results if not r.success)
                color = theme.SUCCESS if fail == 0 else theme.WARNING
                self.after(0, lambda: self._set_status(
                    f"↩  Undo abgeschlossen – {ok} zurück, {fail} Konflikte.", color=color, progress=1.0))
            except Exception as exc:
                msg = str(exc)
                self.after(0, lambda: self._set_status(f"✗  Undo-Fehler: {msg[:100]}", color=theme.ERROR))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_latest_log(self) -> Path | None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        logs = sorted(_LOG_DIR.glob("sorter_*.jsonl"))
        return logs[-1] if logs else None
