"""Main application window – HUD cockpit with animation layer."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import yaml

from src.commands.manager import CommandManager
from src.core.logger import OperationLogger
from src.core.mover import create_folder, move_file
from src.core.scanner import scan_folder
from src.core.undo import undo_session
from src.gui import theme
from src.gui.hud.animation_engine import AnimState, AnimationEngine
from src.llm.ollama_client import OllamaClient, PlanValidationError

_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
_LOG_DIR       = Path(__file__).parent.parent.parent / "logs"
_WINDOW_SIZE   = "960x720"
_WINDOW_TITLE  = "LOCAL-FILE-SORTER  //  HUD v0.1"
_VISION_ENTRY  = "🔍  Vision-Modus (Bilder nach Inhalt)"


# ---------------------------------------------------------------------------
# Settings I/O
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    with _SETTINGS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _save_settings(cfg: dict) -> None:
    with _SETTINGS_PATH.open("w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh, allow_unicode=True, default_flow_style=False)


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
# Settings Dialog (with animation toggles)
# ---------------------------------------------------------------------------

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent: "SorterApp", cfg: dict) -> None:
        super().__init__(parent)
        self._parent = parent
        self._cfg    = cfg
        self.title("Einstellungen")
        self.geometry("500x580")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self.focus_set()
        self._build()

    def _build(self) -> None:
        pad = {"padx": 24, "pady": 8}
        ctk.CTkLabel(self, text="EINSTELLUNGEN", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", **pad)

        self._add_entry("Ollama URL",  self._cfg["ollama"]["base_url"], "_url")
        self._add_entry("Modell",      self._cfg["ollama"]["model"],    "_model")

        ctk.CTkLabel(self, text="APP", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=24, pady=(16, 4))

        self._dry_var = self._add_toggle("Dry-Run (kein echtes Verschieben)",
                                          self._cfg["app"]["dry_run"])

        ctk.CTkLabel(self, text="ANIMATIONEN", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=24, pady=(16, 4))

        ui = self._cfg.get("ui", {})
        self._anim_var  = self._add_toggle("Animationen aktivieren",
                                            ui.get("animations_enabled", True))
        self._reduc_var = self._add_toggle("Reduzierte Bewegung",
                                            ui.get("reduced_motion", False))
        self._boot_var  = self._add_toggle("Boot-Sequenz beim Start",
                                            ui.get("boot_sequence", True))

        ctk.CTkLabel(self, text="VISION", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=24, pady=(16, 4))

        vis = self._cfg.get("vision", {})
        self._vision_enabled_var = self._add_toggle(
            "Vision-Modus aktivieren", vis.get("enabled", False))
        self._add_entry("Vision-Modell",
                        vis.get("model", "moondream:1.8b"), "_vision_model")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(24, 12))
        ctk.CTkButton(row, text="Speichern", width=120,
                      command=self._save, **theme.btn_primary()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Abbrechen", width=120,
                      command=self.destroy, **theme.btn_ghost()).pack(side="right")

    def _add_entry(self, label: str, default: str, attr: str) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=5)
        ctk.CTkLabel(row, text=label, width=130, anchor="w",
                     text_color=theme.TEXT_MUTED, font=theme.FONT_BODY).pack(side="left")
        var = ctk.StringVar(value=default)
        setattr(self, attr, var)
        ctk.CTkEntry(row, textvariable=var, fg_color=theme.SURFACE,
                     border_color=theme.SURFACE_HI, text_color=theme.TEXT,
                     font=theme.FONT_MONO_SM).pack(side="left", fill="x", expand=True)

    def _add_toggle(self, label: str, initial: bool) -> ctk.BooleanVar:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row, text=label, text_color=theme.TEXT,
                     font=theme.FONT_BODY).pack(side="left")
        var = ctk.BooleanVar(value=initial)
        ctk.CTkCheckBox(row, text="", variable=var,
                        fg_color=theme.ACCENT_PRIMARY,
                        checkmark_color=theme.BG_DEEP).pack(side="right")
        return var

    def _save(self) -> None:
        self._cfg["ollama"]["base_url"] = self._url.get().strip()
        self._cfg["ollama"]["model"]    = self._model.get().strip()
        self._cfg["app"]["dry_run"]     = self._dry_var.get()
        if "ui" not in self._cfg:
            self._cfg["ui"] = {}
        self._cfg["ui"]["animations_enabled"] = self._anim_var.get()
        self._cfg["ui"]["reduced_motion"]      = self._reduc_var.get()
        self._cfg["ui"]["boot_sequence"]       = self._boot_var.get()
        if "vision" not in self._cfg:
            self._cfg["vision"] = {}
        self._cfg["vision"]["enabled"] = self._vision_enabled_var.get()
        self._cfg["vision"]["model"]   = self._vision_model.get().strip()
        _save_settings(self._cfg)
        self._parent.reload_settings()
        self.destroy()


# ---------------------------------------------------------------------------
# Plan validation error detail dialog
# ---------------------------------------------------------------------------

class _PlanErrorDialog(ctk.CTkToplevel):
    def __init__(self, parent, detail: str) -> None:
        super().__init__(parent)
        self.title("Plan abgelehnt")
        self.geometry("640x400")
        self.minsize(480, 280)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self.focus_set()
        self._build(detail)

    def _build(self, detail: str) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="PLAN ABGELEHNT", font=theme.FONT_SECTION,
                     text_color=theme.ERROR,
                     ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))

        box = ctk.CTkTextbox(self, fg_color=theme.SURFACE, text_color=theme.TEXT,
                             font=theme.FONT_MONO_SM, state="normal",
                             border_color=theme.ERROR, border_width=1)
        box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        box.insert("end", detail)
        box.configure(state="disabled")

        ctk.CTkButton(self, text="OK", width=100, command=self.destroy,
                      **theme.btn_ghost()).grid(row=2, column=0,
                                                sticky="e", padx=20, pady=(0, 16))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class SorterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        theme.apply_mono_family(theme.resolve_mono_family())

        self.title(_WINDOW_TITLE)
        self.geometry(_WINDOW_SIZE)
        self.minsize(800, 600)
        self.configure(fg_color=theme.BG_DEEP)

        self._cfg: dict           = _load_settings()
        self._folder: Path | None = None
        self._last_log_path: Path | None = self._find_latest_log()
        self._busy = False
        self._vision_mode = False
        self._watcher = None

        # Animation engine (created before UI so widgets can register)
        self._engine  = AnimationEngine(self._cfg)
        self._cmd_mgr = CommandManager()
        self._cmd_map: dict[str, str] = {}  # display name → slug

        self._build_ui()
        self._refresh_command_dropdown()
        self._set_status("Bereit", color=theme.TEXT_MUTED)

        # CoreIndicator floated top-right via place()
        self._attach_core_indicator()

        # Boot sequence (deferred until window is mapped)
        if self._engine.boot_sequence and self._engine.enabled:
            self.after(150, self._start_boot)
        else:
            self._engine.set_state(AnimState.IDLE)

        # Block Enter from triggering execution
        self.bind_all("<Return>",   lambda e: "break" if self._busy else None)
        self.bind_all("<KP_Enter>", lambda e: "break" if self._busy else None)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        self.destroy()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_dry_run_banner()    # row 1 – shown only when dry_run is on
        self._build_folder_section()   # row 2
        self._build_command_section()  # row 3
        self._build_action_row()       # row 4
        self._build_activity_log()     # row 5
        self._build_status_bar()       # row 6

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=52, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, text="⚡  LOCAL-FILE-SORTER",
                     font=theme.FONT_TITLE,
                     text_color=theme.ACCENT_PRIMARY,
                     ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        ctk.CTkLabel(hdr, text="Qwen2.5 7B · Ollama",
                     font=theme.FONT_MONO_SM,
                     text_color=theme.TEXT_MUTED,
                     ).grid(row=0, column=1, sticky="w", padx=6)

        ctk.CTkButton(hdr, text="⚙", width=40, height=32,
                      command=self._open_settings,
                      **theme.btn_ghost(),
                      ).grid(row=0, column=2, padx=(0, 140), pady=10, sticky="e")

    def _build_dry_run_banner(self) -> None:
        self._dry_banner = ctk.CTkFrame(self, fg_color="#7d5a00", height=30, corner_radius=0)
        ctk.CTkLabel(
            self._dry_banner,
            text="⚠  DRY-RUN AKTIV – Dateien werden nicht verschoben",
            font=theme.FONT_MONO_SM,
            text_color="#ffd700",
        ).pack(expand=True)
        self._update_dry_run_banner()

    def _update_dry_run_banner(self) -> None:
        if self._cfg.get("app", {}).get("dry_run", False):
            self._dry_banner.grid(row=1, column=0, sticky="ew")
        else:
            self._dry_banner.grid_remove()

    def _build_folder_section(self) -> None:
        card = ctk.CTkFrame(self, **theme.card())
        card.grid(row=2, column=0, sticky="ew", padx=16, pady=(12, 4))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="ZIELVERZEICHNIS", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED,
                     ).grid(row=0, column=0, columnspan=3, sticky="w",
                            padx=16, pady=(12, 4))

        ctk.CTkButton(card, text="📁  Ordner wählen", width=160,
                      command=self._choose_folder,
                      **theme.btn_ghost(),
                      ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        self._path_label = ctk.CTkLabel(card,
                                         text="— kein Ordner gewählt —",
                                         font=theme.FONT_MONO_SM,
                                         text_color=theme.TEXT_MUTED, anchor="w")
        self._path_label.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="ew")

        self._recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(card, text="Unterordner einbeziehen",
                        variable=self._recursive_var,
                        font=theme.FONT_BODY_SM, text_color=theme.TEXT,
                        fg_color=theme.ACCENT_PRIMARY,
                        checkmark_color=theme.BG_DEEP,
                        hover_color=theme.ACCENT_DIM,
                        ).grid(row=1, column=2, padx=16, pady=(0, 12), sticky="e")

    def _build_command_section(self) -> None:
        card = ctk.CTkFrame(self, **theme.card())
        card.grid(row=3, column=0, sticky="nsew", padx=16, pady=4)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(card, text="SORTIERBEFEHL", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED,
                     ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        # Controls row: dropdown + save/manage buttons
        ctrl = ctk.CTkFrame(card, fg_color="transparent")
        ctrl.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self._saved_cmd_var = ctk.StringVar(value="— Gespeicherte Befehle —")
        self._cmd_menu = ctk.CTkOptionMenu(
            ctrl,
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
        self._cmd_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(ctrl, text="💾  Speichern", width=130,
                      command=self._open_save_command_dialog,
                      **theme.btn_ghost()).pack(side="left", padx=(0, 6))

        ctk.CTkButton(ctrl, text="📂  Verwalten", width=130,
                      command=self._open_manage_commands_dialog,
                      **theme.btn_ghost()).pack(side="left")

        self._cmd_box = ctk.CTkTextbox(
            card, height=90,
            fg_color=theme.SURFACE_HI,
            border_color=theme.SURFACE_HI, border_width=1,
            text_color=theme.TEXT,
            font=theme.FONT_MONO, corner_radius=6, wrap="word",
        )
        self._cmd_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 4))
        self._cmd_box.insert("end", "Sortiere nach Dateiendung in Unterordner")
        self._cmd_box.bind("<Return>", lambda e: None)

        # WaveformIndicator below command box
        try:
            from src.gui.hud.widgets.waveform import WaveformIndicator
            self._wave = WaveformIndicator(card, self._engine)
            self._wave.grid(row=3, column=0, padx=16, pady=(2, 12), sticky="w")
        except Exception:
            pass

    def _build_action_row(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=4, column=0, sticky="ew", padx=16, pady=8)

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

        self._watch_btn = ctk.CTkButton(row, text="👁  Watcher starten", width=180,
                                         command=self._on_toggle_watcher,
                                         **theme.btn_ghost())
        self._watch_btn.pack(side="left", padx=(10, 0))

    def _build_activity_log(self) -> None:
        card = ctk.CTkFrame(self, **theme.card())
        card.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        ctk.CTkLabel(hdr, text="AKTIVITÄTSLOG", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkButton(hdr, text="✕ Leeren", width=80, height=22,
                      command=self._clear_log,
                      **theme.btn_ghost()).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            card, height=110,
            fg_color=theme.SURFACE_HI,
            border_color=theme.SURFACE_HI, border_width=0,
            text_color=theme.TEXT_MUTED,
            font=theme.FONT_MONO_SM,
            corner_radius=4, wrap="none", state="disabled",
        )
        self._log_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=34, corner_radius=0)
        bar.grid(row=6, column=0, sticky="ew")
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
    # CoreIndicator overlay
    # ------------------------------------------------------------------

    def _attach_core_indicator(self) -> None:
        try:
            from src.gui.hud.widgets.core_indicator import CoreIndicator
            self._core = CoreIndicator(self, self._engine)
            # Float top-right; re-place on resize
            self._place_core()
            self.bind("<Configure>", lambda _: self._place_core(), add="+")
        except Exception:
            pass

    def _place_core(self) -> None:
        try:
            self._core.place(relx=1.0, rely=0.0, x=-128, y=8,
                              width=120, height=120)
            self._core.lift()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Boot sequence
    # ------------------------------------------------------------------

    def _start_boot(self) -> None:
        try:
            from src.gui.hud.widgets.boot_sequence import BootSequence
            boot = BootSequence(self, on_done=lambda: self._engine.set_state(AnimState.IDLE))
            self.after(80, boot.start)
        except Exception:
            self._engine.set_state(AnimState.IDLE)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, color: str = theme.TEXT_MUTED,
                    progress: float | None = None) -> None:
        self._status_label.configure(text=msg, text_color=color)
        self._status_dot.configure(text_color=color)
        if progress is not None:
            self._progress.set(progress)

    def _set_engine_state(self, state: AnimState) -> None:
        try:
            self._engine.set_state(state)
        except Exception:
            pass

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        st = "disabled" if busy else "normal"
        self._plan_btn.configure(state=st)
        self._undo_btn.configure(state=st)

    def _log(self, msg: str) -> None:
        """Append a timestamped message to the activity log (thread-safe)."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"
        def _append():
            if not self.winfo_exists():
                return
            self._log_box.configure(state="normal")
            self._log_box.insert("end", line)
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _append)

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def reload_settings(self) -> None:
        self._cfg = _load_settings()
        try:
            self._engine.update_settings(self._cfg)
        except Exception:
            pass
        self._update_dry_run_banner()
        self._refresh_command_dropdown()

    def _find_latest_log(self) -> Path | None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        logs = sorted(_LOG_DIR.glob("sorter_*.jsonl"))
        return logs[-1] if logs else None

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _stop_watcher_if_running(self, reason: str) -> None:
        if self._watcher is not None and self._watcher.is_running:
            self._watcher.stop()
            self._watcher = None
            self._watch_btn.configure(text="👁  Watcher starten",
                                       fg_color=theme.SURFACE_HI, text_color=theme.TEXT)
            self._log(f"Ordner-Watcher gestoppt ({reason}).")

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Zielverzeichnis wählen")
        if folder:
            self._stop_watcher_if_running("Ordner gewechselt")
            self._folder = Path(folder)
            self._path_label.configure(text=str(self._folder),
                                        text_color=theme.TEXT)

    def _refresh_command_dropdown(self) -> None:
        metas = self._cmd_mgr.list_commands()
        self._cmd_map = {m.name: m.slug for m in metas}
        names = [m.name for m in metas]
        placeholder = "— Gespeicherte Befehle —"
        values = [placeholder] + names
        if self._cfg.get("vision", {}).get("enabled", False):
            values.append(_VISION_ENTRY)
        self._cmd_menu.configure(values=values)
        self._saved_cmd_var.set(placeholder)

    def _on_saved_command(self, choice: str) -> None:
        if choice.startswith("—"):
            self._vision_mode = False
            return
        if choice == _VISION_ENTRY:
            self._vision_mode = True
            self._cmd_box.delete("1.0", "end")
            self._cmd_box.insert(
                "end",
                "[Vision-Modus] Bilder werden per KI-Bildanalyse nach Inhalt sortiert.")
            return
        self._vision_mode = False
        slug = self._cmd_map.get(choice)
        if slug is None:
            return
        try:
            cmd = self._cmd_mgr.load_command(slug)
        except Exception:
            return
        self._cmd_box.delete("1.0", "end")
        self._cmd_box.insert("end", cmd.prompt_text)
        self._recursive_var.set(cmd.default_recursive)
        if cmd.target_folder:
            folder = Path(cmd.target_folder)
            if folder.is_dir():
                self._stop_watcher_if_running("Regelprofil geladen")
                self._folder = folder
                self._path_label.configure(text=str(folder), text_color=theme.TEXT)
                self._log(f"Regelprofil geladen: Zielordner → {folder}")
            else:
                self._log(f"⚠ Regelprofil-Ordner nicht gefunden: {folder}")

    def _open_save_command_dialog(self) -> None:
        from src.gui.commands_dialogs import SaveCommandDialog
        SaveCommandDialog(
            self, self._cmd_mgr,
            prompt_text=self._cmd_box.get("1.0", "end").strip(),
            recursive=self._recursive_var.get(),
            target_folder=str(self._folder) if self._folder else "",
            on_saved=self._refresh_command_dropdown,
        )

    def _open_manage_commands_dialog(self) -> None:
        from src.gui.commands_dialogs import ManageCommandsDialog
        ManageCommandsDialog(self, self._cmd_mgr,
                             on_changed=self._refresh_command_dropdown)

    def _open_settings(self) -> None:
        SettingsDialog(self, self._cfg)

    def _open_log_viewer(self) -> None:
        from src.gui.log_viewer import LogViewer
        LogViewer(self, log_path=self._last_log_path)

    # ------------------------------------------------------------------
    # Plan generation
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
        self.after(0, lambda: self._set_engine_state(AnimState.SCANNING))

        threading.Thread(target=self._generate_plan_worker,
                         args=(command,), daemon=True).start()

    def _generate_plan_worker(self, command: str) -> None:
        try:
            self._log(f"Scan: {self._folder}")
            files = scan_folder(self._folder, recursive=self._recursive_var.get())
            files = [f for f in files if not f.is_dir]
            self._log(f"Scan abgeschlossen: {len(files)} Datei(en) gefunden.")

            if not files:
                self.after(0, lambda: self._set_status(
                    "⚠  Keine Dateien im Verzeichnis.", color=theme.WARNING))
                self.after(0, lambda: self._set_busy(False))
                self.after(0, lambda: self._set_engine_state(AnimState.IDLE))
                return

            if self._vision_mode:
                self._generate_plan_vision(files)
                return

            # --- Quick-plan check (no LLM needed) ---
            from src.llm.quick_planner import try_quick_plan
            quick = try_quick_plan(command, files, self._folder)
            if quick is not None:
                n = len(quick.actions)
                self._log(f"Schnellplan (kein LLM-Aufruf): {n} Aktion(en). {quick.summary}")
                self.after(0, lambda: self._set_status(
                    f"Schnellplan erstellt ({n} Aktionen) – kein LLM-Aufruf nötig.",
                    color=theme.ACCENT_PRIMARY, progress=1.0))
                self.after(0, lambda: self._on_plan_ready(quick))
                return

            # --- LLM path ---
            model_name = self._cfg["ollama"]["model"]
            self._log(f"Sende Anfrage an Modell: {model_name}")
            self.after(0, lambda: self._set_status(
                f"Frage Modell … ({len(files)} Dateien)",
                color=theme.ACCENT_PRIMARY, progress=0.45))
            self.after(0, lambda: self._set_engine_state(AnimState.THINKING))

            batch_size = self._cfg.get("app", {}).get("max_files_per_batch", 100)

            def _progress_cb(chunk: int, total: int) -> None:
                self._log(f"Chunk {chunk}/{total} verarbeitet.")
                if total > 1:
                    self.after(0, lambda c=chunk, t=total: self._set_status(
                        f"Verarbeite Chunk {c}/{t} …",
                        color=theme.ACCENT_PRIMARY))

            client = OllamaClient(model=model_name,
                                   base_url=self._cfg["ollama"]["base_url"])
            plan, _ = client.generate_plan(
                files=files, user_command=command,
                target_folder=self._folder,
                batch_size=batch_size,
                progress_cb=_progress_cb,
            )
            self._log(f"Plan empfangen: {len(plan.actions)} Aktion(en). Validierung OK.")
            self.after(0, lambda: self._on_plan_ready(plan))

        except PlanValidationError as exc:
            detail = str(exc)
            self._log(f"FEHLER – Plan abgelehnt: {str(exc)[:200]}")
            self.after(0, lambda d=detail: _PlanErrorDialog(self, d))
            self.after(0, lambda: self._set_status(
                "⚠  Plan abgelehnt – Details im Dialog.", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, lambda: self._set_engine_state(AnimState.ERROR))
        except Exception as exc:
            msg = str(exc)
            self._log(f"FEHLER: {msg[:200]}")
            if "refused" in msg.lower() or "connect" in msg.lower():
                human = "Modell nicht erreichbar – läuft Ollama?"
            elif "404" in msg or "not found" in msg.lower():
                model = self._cfg.get("ollama", {}).get("model", "qwen2.5:7b-instruct-q4_K_M")
                human = f"Modell nicht gefunden → ollama pull {model}"
            else:
                human = f"Fehler: {msg[:120]}"
            self.after(0, lambda h=human: self._set_status(f"✗  {h}", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, lambda: self._set_engine_state(AnimState.ERROR))

    def _generate_plan_vision(self, files) -> None:
        """Vision-branch: classify images, build and validate plan."""
        try:
            from src.llm.ollama_client import validate_plan
            from src.llm.vision_client import VisionClient
            from src.llm.vision_sorter import build_vision_plan

            vision_cfg   = self._cfg.get("vision", {})
            allowed_exts = {
                e.lower() for e in vision_cfg.get(
                    "allowed_extensions",
                    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
                )
            }
            images = [f for f in files if f.extension in allowed_exts]

            if not images:
                self.after(0, lambda: self._set_status(
                    "⚠  Keine Bilder im Verzeichnis.", color=theme.WARNING))
                self.after(0, lambda: self._set_busy(False))
                self.after(0, lambda: self._set_engine_state(AnimState.IDLE))
                return

            n = len(images)
            self.after(0, lambda: self._set_status(
                f"Vision – analysiere {n} Bild{'er' if n != 1 else ''} …",
                color=theme.ACCENT_PRIMARY, progress=0.3))
            self.after(0, lambda: self._set_engine_state(AnimState.THINKING))

            def _progress_cb(done: int, total: int) -> None:
                self.after(0, lambda d=done, t=total: self._set_status(
                    f"Vision – Bild {d}/{t} …",
                    color=theme.ACCENT_PRIMARY,
                    progress=0.3 + 0.6 * (d / t)))

            client = VisionClient(
                model=vision_cfg.get("model", "moondream:1.8b"),
                base_url=self._cfg["ollama"]["base_url"],
            )
            image_paths = [f.path for f in images]
            classifications = client.classify_batch(image_paths, progress_cb=_progress_cb)

            plan = build_vision_plan(classifications, self._folder)
            validate_plan(plan, self._folder)
            self.after(0, lambda: self._on_plan_ready(plan))

        except PlanValidationError as exc:
            detail = str(exc)
            self.after(0, lambda d=detail: _PlanErrorDialog(self, d))
            self.after(0, lambda: self._set_status(
                "⚠  Vision-Plan abgelehnt – Details im Dialog.", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, lambda: self._set_engine_state(AnimState.ERROR))
        except Exception as exc:
            msg = str(exc)
            if "refused" in msg.lower() or "connect" in msg.lower():
                human = "Vision-Modell nicht erreichbar – läuft Ollama?"
            elif "404" in msg or "not found" in msg.lower():
                model = self._cfg.get("vision", {}).get("model", "moondream:1.8b")
                human = f"Vision-Modell nicht gefunden → ollama pull {model}"
            else:
                human = f"Vision-Fehler: {msg[:120]}"
            self.after(0, lambda h=human: self._set_status(f"✗  {h}", color=theme.ERROR))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, lambda: self._set_engine_state(AnimState.ERROR))

    def _on_plan_ready(self, plan) -> None:
        from src.gui.preview_dialog import PreviewDialog
        self._set_engine_state(AnimState.IDLE)
        self._set_status("Plan empfangen – Vorschau …", color=theme.SUCCESS, progress=0.9)
        dlg = PreviewDialog(
            parent=self, plan=plan, target_folder=self._folder,
            log_dir=_LOG_DIR, dry_run=self._cfg["app"]["dry_run"],
            engine=self._engine,
            on_complete=self._on_execution_complete,
        )
        dlg.grab_set()
        self._set_busy(False)

    def _on_execution_complete(self, ok: int, fail: int, log_path: Path) -> None:
        self._last_log_path = log_path
        color = theme.SUCCESS if fail == 0 else theme.WARNING
        self._log(f"Ausführung abgeschlossen: {ok} ✓  {fail} ✗  – Log: {log_path.name}")
        self._set_status(
            f"✓ Fertig – {ok} erfolgreich, {fail} fehlgeschlagen.  Log: {log_path.name}",
            color=color, progress=1.0)
        self._set_engine_state(AnimState.SUCCESS)
        self.after(600, lambda: self._set_engine_state(AnimState.IDLE))

    # ------------------------------------------------------------------
    # Folder watcher
    # ------------------------------------------------------------------

    def _on_toggle_watcher(self) -> None:
        if self._watcher is not None and self._watcher.is_running:
            self._watcher.stop()
            self._watcher = None
            self._watch_btn.configure(text="👁  Watcher starten",
                                       fg_color=theme.SURFACE_HI, text_color=theme.TEXT)
            self._log("Ordner-Watcher gestoppt.")
            return

        if self._folder is None or not self._folder.is_dir():
            self._set_status("⚠  Kein gültiger Ordner für Watcher gewählt.", color=theme.WARNING)
            return

        from src.core.watcher import FolderWatcher
        interval = self._cfg.get("watcher", {}).get("poll_interval_seconds", 5)
        self._watcher = FolderWatcher(
            folder=self._folder,
            on_new_files=self._on_watcher_new_files,
            recursive=self._recursive_var.get(),
            poll_interval=interval,
        )
        self._watcher.start()
        self._watch_btn.configure(text="⏹  Watcher stoppen",
                                   fg_color=theme.ACCENT_PRIMARY, text_color=theme.BG_DEEP)
        self._log(f"Ordner-Watcher gestartet: {self._folder}  (alle {interval}s)")

    def _on_watcher_new_files(self, new_files: list) -> None:
        """Called from the watcher's background thread — marshal to the main thread."""
        self.after(0, lambda: self._handle_watcher_new_files(new_files))

    def _handle_watcher_new_files(self, new_files: list) -> None:
        if not self.winfo_exists():
            return
        n = len(new_files)
        self._log(f"🔔 Watcher: {n} neue Datei(en) erkannt.")

        if self._busy:
            self._log("Watcher: übersprungen (Programm gerade beschäftigt).")
            return
        if self._vision_mode:
            self._log("Watcher: Vision-Modus aktiv – bitte manuell 'Plan generieren' klicken.")
            return
        command = self._cmd_box.get("1.0", "end").strip()
        if not command:
            self._log("Watcher: kein Befehl gesetzt – bitte manuell 'Plan generieren' klicken.")
            return

        self._set_status(f"👁  Watcher: {n} neue Datei(en) – erstelle Plan …",
                         color=theme.ACCENT_PRIMARY)
        self._on_generate_plan()

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        log_path = self._last_log_path
        if log_path is None or not log_path.exists():
            self._set_status("⚠  Kein Session-Log gefunden.", color=theme.WARNING)
            return
        self._set_busy(True)
        self._set_status("Mache letzte Session rückgängig …",
                         color=theme.ACCENT_PRIMARY, progress=0.2)
        self._set_engine_state(AnimState.EXECUTING)

        def _worker():
            try:
                self._log(f"Undo: lese Session-Log {log_path.name}")
                results = undo_session(log_path)
                ok   = sum(1 for r in results if r.success)
                fail = sum(1 for r in results if not r.success)
                self._log(f"Undo abgeschlossen: {ok} zurück, {fail} Konflikte.")
                for r in results:
                    if not r.success and r.error:
                        self._log(f"  Konflikt: {r.error[:120]}")
                color = theme.SUCCESS if fail == 0 else theme.WARNING
                self.after(0, lambda: self._set_status(
                    f"↩  Undo – {ok} zurück, {fail} Konflikte.", color=color, progress=1.0))
                self.after(0, lambda: self._set_engine_state(
                    AnimState.SUCCESS if fail == 0 else AnimState.ERROR))
                self.after(700, lambda: self._set_engine_state(AnimState.IDLE))
            except Exception as exc:
                msg = str(exc)
                self._log(f"Undo FEHLER: {msg[:200]}")
                self.after(0, lambda: self._set_status(
                    f"✗  Undo-Fehler: {msg[:100]}", color=theme.ERROR))
                self.after(0, lambda: self._set_engine_state(AnimState.ERROR))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_worker, daemon=True).start()
