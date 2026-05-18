"""Modal plan preview – review, confirm, execute, and track progress."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.core.logger import OperationLogger
from src.core.mover import create_folder, move_file
from src.gui import theme
from src.llm.schemas import OpType, SortPlan

_PLAN_EXPORT_DIR = Path(__file__).parent.parent.parent / "logs" / "plans"


class PreviewDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        plan: SortPlan,
        target_folder: Path,
        log_dir: Path,
        dry_run: bool = False,
        on_complete: Callable[[int, int, Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._plan          = plan
        self._target_folder = target_folder
        self._log_dir       = log_dir
        self._dry_run       = dry_run
        self._on_complete   = on_complete
        self._executing     = False

        self.title("Sortierplan – Vorschau")
        self.geometry("900x620")
        self.minsize(720, 480)
        self.configure(fg_color=theme.BG_DEEP)
        self.resizable(True, True)

        self._build()
        self._populate_tree()

        # Prevent accidental Enter execution
        self.bind("<Return>",   lambda e: "break")
        self.bind("<KP_Enter>", lambda e: "break")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Summary
        summary_frame = ctk.CTkFrame(self, **theme.card())
        summary_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        summary_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(summary_frame, text="ZUSAMMENFASSUNG", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 2))

        dry_tag = "  [DRY-RUN – nichts wird wirklich verschoben]" if self._dry_run else ""
        ctk.CTkLabel(summary_frame, text=self._plan.summary + dry_tag,
                     font=theme.FONT_BODY, text_color=theme.ACCENT_PRIMARY,
                     wraplength=840, anchor="w",
                     ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Treeview container
        tree_frame = ctk.CTkFrame(self, **theme.card())
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._tree = self._build_tree(tree_frame)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=8)

        # Progress bar (hidden until execution starts)
        self._progress = ctk.CTkProgressBar(self, fg_color=theme.SURFACE_HI,
                                             progress_color=theme.ACCENT_PRIMARY,
                                             height=6, corner_radius=0)
        self._progress.grid(row=2, column=0, sticky="ew")
        self._progress.set(0)

        # Result label
        self._result_label = ctk.CTkLabel(self, text="", font=theme.FONT_MONO_SM,
                                           text_color=theme.TEXT_MUTED)
        self._result_label.grid(row=3, column=0, sticky="w", padx=16, pady=(4, 0))

        # Button row
        self._build_buttons()

    def _build_tree(self, parent) -> ttk.Treeview:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("HUD.Treeview",
                        background=theme.SURFACE,
                        foreground=theme.TEXT,
                        fieldbackground=theme.SURFACE,
                        borderwidth=0,
                        font=theme.FONT_MONO_SM,
                        rowheight=26)
        style.configure("HUD.Treeview.Heading",
                        background=theme.SURFACE_HI,
                        foreground=theme.ACCENT_PRIMARY,
                        font=theme.FONT_MONO_BOLD,
                        borderwidth=0,
                        relief="flat")
        style.map("HUD.Treeview",
                  background=[("selected", theme.SURFACE_HI)],
                  foreground=[("selected", theme.ACCENT_PRIMARY)])
        style.map("HUD.Treeview.Heading",
                  background=[("active", theme.SURFACE_HI)])

        tree = ttk.Treeview(parent, style="HUD.Treeview",
                            columns=("op", "source", "destination", "reason"),
                            show="headings", selectmode="browse")
        tree.heading("op",          text=" Op",          anchor="w")
        tree.heading("source",      text=" Source",      anchor="w")
        tree.heading("destination", text=" Destination", anchor="w")
        tree.heading("reason",      text=" Grund",       anchor="w")

        tree.column("op",          width=120, minwidth=80,  stretch=False)
        tree.column("source",      width=220, minwidth=100, stretch=True)
        tree.column("destination", width=220, minwidth=100, stretch=True)
        tree.column("reason",      width=180, minwidth=80,  stretch=True)

        tree.tag_configure("folder", foreground=theme.ACCENT_DIM)
        tree.tag_configure("move",   foreground=theme.TEXT)
        tree.tag_configure("done",   foreground=theme.SUCCESS)
        tree.tag_configure("fail",   foreground=theme.ERROR)
        return tree

    def _build_buttons(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=4, column=0, sticky="ew", padx=16, pady=12)

        self._exec_btn = ctk.CTkButton(row, text="✓  Ausführen",  width=160,
                                        command=self._on_execute,
                                        **theme.btn_success())
        self._exec_btn.pack(side="left", padx=(0, 10))

        self._cancel_btn = ctk.CTkButton(row, text="✗  Abbrechen", width=140,
                                          command=self.destroy,
                                          **theme.btn_danger())
        self._cancel_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(row, text="⬇  JSON exportieren", width=180,
                      command=self._export_json,
                      **theme.btn_ghost()).pack(side="left")

        n = len(self._plan.actions)
        ctk.CTkLabel(row, text=f"{n} Aktionen",
                     font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED,
                     ).pack(side="right")

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        for action in self._plan.actions:
            if action.op_type == OpType.create_folder:
                op_str  = "[+] create_folder"
                src_str = "—"
                tag     = "folder"
            else:
                op_str  = "[→] move"
                src_str = str(action.source) if action.source else "—"
                tag     = "move"
            self._tree.insert("", "end", values=(
                op_str, src_str, str(action.destination), action.reason,
            ), tags=(tag,))

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _on_execute(self) -> None:
        n = len(self._plan.actions)
        dry_note = "\n\n[DRY-RUN aktiv – kein echtes Verschieben]" if self._dry_run else ""

        confirmed = messagebox.askyesno(
            title="Ausführung bestätigen",
            message=(
                f"{n} Aktion(en) werden ausgeführt.\n"
                f"Diese sind über 'Undo letzte Session' umkehrbar.\n"
                f"{dry_note}"
                f"\nFortfahren?"
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._executing = True
        self._exec_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._progress.set(0)

        threading.Thread(target=self._execute_worker, daemon=True).start()

    def _execute_worker(self) -> None:
        logger = OperationLogger(self._log_dir)
        actions = self._plan.actions
        total   = len(actions)
        ok_count   = 0
        fail_count = 0

        items = self._tree.get_children()

        for i, action in enumerate(actions):
            progress = (i + 1) / total
            self.after(0, lambda p=progress: self._progress.set(p))

            if action.op_type == OpType.create_folder:
                if not self._dry_run:
                    success = create_folder(action.destination)
                else:
                    success = True
                logger.log_folder(action.destination, success)
                tag  = "done" if success else "fail"
                if success:
                    ok_count += 1
                else:
                    fail_count += 1
            else:
                if action.source is None:
                    logger.log_error("move ohne source", {"action": str(action)})
                    fail_count += 1
                    tag = "fail"
                else:
                    if not self._dry_run:
                        result = move_file(action.source, action.destination)
                    else:
                        from src.core.mover import MoveResult
                        result = MoveResult(
                            success=True,
                            source_original=action.source,
                            destination_final=action.destination,
                        )
                    logger.log_move(result)
                    if result.success:
                        ok_count += 1
                        tag = "done"
                    else:
                        fail_count += 1
                        tag = "fail"

            if i < len(items):
                item_id = items[i]
                current_vals = self._tree.item(item_id, "values")
                self.after(0, lambda iid=item_id, t=tag, v=current_vals: (
                    self._tree.item(iid, tags=(t,)),
                ))

            status_color = theme.SUCCESS if fail_count == 0 else theme.WARNING
            msg = f"{ok_count} ✓  {fail_count} ✗  –  {i + 1}/{total}"
            self.after(0, lambda m=msg, c=status_color: (
                self._result_label.configure(text=m, text_color=c),
            ))

        logger.close()
        log_path = logger.get_session_path()

        final_color = theme.SUCCESS if fail_count == 0 else theme.WARNING
        final_msg   = f"Abgeschlossen: {ok_count} erfolgreich, {fail_count} fehlgeschlagen."
        self.after(0, lambda: self._result_label.configure(text=final_msg, text_color=final_color))
        self.after(0, lambda: self._exec_btn.configure(state="normal", text="✓  Nochmal"))
        self.after(0, lambda: self._cancel_btn.configure(state="normal", text="✗  Schließen"))

        if self._on_complete:
            self.after(0, lambda: self._on_complete(ok_count, fail_count, log_path))

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    def _export_json(self) -> None:
        import datetime as dt
        _PLAN_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = _PLAN_EXPORT_DIR / f"plan_{ts}.json"

        payload = {
            "summary": self._plan.summary,
            "target_folder": str(self._target_folder),
            "actions": [
                {
                    "op_type":     a.op_type.value,
                    "source":      str(a.source) if a.source else None,
                    "destination": str(a.destination),
                    "reason":      a.reason,
                }
                for a in self._plan.actions
            ],
        }
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._result_label.configure(
            text=f"Exportiert: {dest.name}", text_color=theme.ACCENT_DIM,
        )
