"""Modal plan preview – review, confirm, execute with animation integration."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.core.logger import OperationLogger
from src.core.mover import MoveResult, create_folder, is_duplicate, move_file, resolve_conflict
from src.gui import theme
from src.gui.hud.animation_engine import AnimState, AnimationEngine
from src.llm.schemas import OpType, SortPlan

_PLAN_EXPORT_DIR = Path(__file__).parent.parent.parent / "logs" / "plans"
_REVEAL_DELAY_MS = 50   # ms between each row appearing


class PreviewDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        plan: SortPlan,
        target_folder: Path,
        log_dir: Path,
        dry_run: bool = False,
        engine: AnimationEngine | None = None,
        on_complete: Callable[[int, int, Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._plan          = plan
        self._target_folder = target_folder
        self._log_dir       = log_dir
        self._dry_run       = dry_run
        self._engine        = engine
        self._on_complete   = on_complete
        self._executing     = False
        self._activity      = None   # ActivityStream widget (optional)

        # Grouping state: destination-folder path (str) -> tree iid
        self._folder_iid: dict[str, str] = {}
        self._folder_count: dict[str, int] = {}
        # plan.actions index -> tree iid (survives grouping/reordering)
        self._action_iid: dict[int, str] = {}

        self.title("Sortierplan – Vorschau")
        self.geometry("920x660")
        self.minsize(720, 500)
        self.configure(fg_color=theme.BG_DEEP)
        self.resizable(True, True)

        self._build()
        self._reveal_rows()   # PlanRevealAnimation

        self.bind("<Return>",   lambda e: "break")
        self.bind("<KP_Enter>", lambda e: "break")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Summary
        sf = ctk.CTkFrame(self, **theme.card())
        sf.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        sf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sf, text="ZUSAMMENFASSUNG", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED,
                     ).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 2))
        dry_tag = "  [DRY-RUN]" if self._dry_run else ""
        ctk.CTkLabel(sf, text=self._plan.summary + dry_tag,
                     font=theme.FONT_BODY, text_color=theme.ACCENT_PRIMARY,
                     wraplength=860, anchor="w",
                     ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Treeview
        tf = ctk.CTkFrame(self, **theme.card())
        tf.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)
        self._tree = self._build_tree(tf)
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=8)

        # ActivityStream
        try:
            from src.gui.hud.widgets.activity_stream import ActivityStream
            if self._engine is not None:
                self._activity = ActivityStream(self, self._engine)
                self._activity.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 0))
        except Exception:
            pass

        # Progress
        self._progress = ctk.CTkProgressBar(self, fg_color=theme.SURFACE_HI,
                                             progress_color=theme.ACCENT_PRIMARY,
                                             height=6, corner_radius=0)
        self._progress.grid(row=3, column=0, sticky="ew")
        self._progress.set(0)

        # Status row: current file (left) + running result (right)
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 0))
        status_row.grid_columnconfigure(0, weight=1)

        self._current_label = ctk.CTkLabel(status_row, text="", font=theme.FONT_MONO_SM,
                                            text_color=theme.ACCENT_DIM, anchor="w")
        self._current_label.grid(row=0, column=0, sticky="w")

        self._result_label = ctk.CTkLabel(status_row, text="", font=theme.FONT_MONO_SM,
                                           text_color=theme.TEXT_MUTED, anchor="e")
        self._result_label.grid(row=0, column=1, sticky="e")

        self._build_buttons()

    def _build_tree(self, parent) -> ttk.Treeview:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("HUD.Treeview",
                        background=theme.SURFACE, foreground=theme.TEXT,
                        fieldbackground=theme.SURFACE, borderwidth=0,
                        font=theme.FONT_MONO_SM, rowheight=26)
        style.configure("HUD.Treeview.Heading",
                        background=theme.SURFACE_HI, foreground=theme.ACCENT_PRIMARY,
                        font=theme.FONT_MONO_BOLD, borderwidth=0, relief="flat")
        style.map("HUD.Treeview",
                  background=[("selected", theme.SURFACE_HI)],
                  foreground=[("selected", theme.ACCENT_PRIMARY)])
        style.map("HUD.Treeview.Heading",
                  background=[("active", theme.SURFACE_HI)])

        tree = ttk.Treeview(parent, style="HUD.Treeview",
                            columns=("op", "source", "destination", "reason"),
                            show="headings", selectmode="browse")
        tree.heading("op",          text=" Op",          anchor="w")
        tree.heading("source",      text=" Von",         anchor="w")
        tree.heading("destination", text=" Nach (Zielordner ⌄ Datei)", anchor="w")
        tree.heading("reason",      text=" Grund",       anchor="w")
        tree.column("op",          width=130, minwidth=80,  stretch=False)
        tree.column("source",      width=220, minwidth=100, stretch=True)
        tree.column("destination", width=260, minwidth=120, stretch=True)
        tree.column("reason",      width=180, minwidth=80,  stretch=True)
        tree.tag_configure("folder",    foreground=theme.ACCENT_DIM)
        tree.tag_configure("move",      foreground=theme.TEXT)
        tree.tag_configure("conflict",  foreground=theme.WARNING)
        tree.tag_configure("duplicate", foreground=theme.ACCENT_DIM)
        tree.tag_configure("done",      foreground=theme.SUCCESS)
        tree.tag_configure("fail",      foreground=theme.ERROR)
        tree.tag_configure("pending",   foreground=theme.TEXT_MUTED)
        return tree

    def _build_buttons(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=16, pady=12)

        self._exec_btn = ctk.CTkButton(row, text="✓  Ausführen", width=160,
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
        ctk.CTkLabel(row, text=f"{n} Aktionen", font=theme.FONT_MONO_SM,
                     text_color=theme.TEXT_MUTED).pack(side="right")

    # ------------------------------------------------------------------
    # PlanRevealAnimation – sequential row insertion with delay
    # ------------------------------------------------------------------

    def _reveal_rows(self) -> None:
        """Insert treeview rows one by one with _REVEAL_DELAY_MS gap."""
        for i, action in enumerate(self._plan.actions):
            self.after(i * _REVEAL_DELAY_MS, lambda idx=i, a=action: self._insert_row(idx, a))

    def _get_or_create_folder_node(self, folder_path: Path, reason: str = "Zielordner") -> str:
        """Return the tree iid for the "before → after" folder bucket, creating it on first use."""
        key = str(folder_path)
        if key in self._folder_iid:
            return self._folder_iid[key]
        iid = self._tree.insert("", "end", values=(
            "[📁]", "—", str(folder_path), reason,
        ), tags=("folder",), open=True)
        self._folder_iid[key] = iid
        self._folder_count[key] = 0
        return iid

    def _insert_row(self, index: int, action) -> None:
        if not self.winfo_exists():
            return

        if action.op_type == OpType.create_folder:
            key = str(action.destination)
            if key in self._folder_iid:
                # A move to this folder already created the header row — reuse it,
                # keeping the running file-count that column already shows.
                iid = self._folder_iid[key]
                count_str = self._tree.item(iid, "values")[1]
                self._tree.item(iid, values=("[📁]", count_str, str(action.destination), action.reason))
            else:
                iid = self._get_or_create_folder_node(action.destination, action.reason)
            self._action_iid[index] = iid
            self._tree.see(iid)
            return

        # move action → child row under its destination folder's bucket
        parent_iid = self._get_or_create_folder_node(action.destination.parent)
        key = str(action.destination.parent)
        self._folder_count[key] = self._folder_count.get(key, 0) + 1
        self._tree.item(parent_iid, values=(
            "[📁]", f"{self._folder_count[key]} Datei(en)",
            str(action.destination.parent),
            self._tree.item(parent_iid, "values")[3],
        ))

        src_str = str(action.source) if action.source else "—"
        reason  = action.reason
        tag     = "move"
        if action.destination and action.destination.exists():
            if action.source and action.source.exists() and is_duplicate(action.source, action.destination):
                reason = f"⧉ Duplikat – wandert nach _Duplikate/  ({action.reason})"
                tag    = "duplicate"
            else:
                final = resolve_conflict(action.destination)
                reason = f"⚠ → {final.name}  ({action.reason})"
                tag    = "conflict"

        dest_name = action.destination.name if action.destination else "—"
        iid = self._tree.insert(parent_iid, "end", values=(
            "[→] move", src_str, dest_name, reason,
        ), tags=(tag,))
        self._action_iid[index] = iid

        # Brief highlight flash: set to pending, restore after 250 ms
        self._tree.item(iid, tags=("pending",))
        self.after(250, lambda i=iid, t=tag: (
            self._tree.item(i, tags=(t,)) if self.winfo_exists() else None
        ))
        self._tree.see(iid)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _on_execute(self) -> None:
        n = len(self._plan.actions)
        dry_note = "\n\n[DRY-RUN aktiv – kein echtes Verschieben]" if self._dry_run else ""
        confirmed = messagebox.askyesno(
            title="Ausführung bestätigen",
            message=(f"{n} Aktion(en) werden ausgeführt.\n"
                     f"Umkehrbar über 'Undo letzte Session'.{dry_note}\nFortfahren?"),
            parent=self,
        )
        if not confirmed:
            return

        self._executing = True
        self._exec_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._progress.set(0)

        if self._engine:
            try:
                self._engine.set_state(AnimState.EXECUTING)
            except Exception:
                pass

        threading.Thread(target=self._execute_worker, daemon=True).start()

    def _execute_worker(self) -> None:
        logger  = OperationLogger(self._log_dir)
        actions = self._plan.actions
        total   = len(actions)
        ok_count = fail_count = 0
        dup_count = 0

        for i, action in enumerate(actions):
            progress = (i + 1) / total
            self.after(0, lambda p=progress: self._progress.set(p))

            current_name = (action.source.name if action.source
                             else action.destination.name)
            current_msg = (f"→ {current_name} …" if action.op_type == OpType.move
                            else f"📁 {action.destination.name} …")
            self.after(0, lambda m=current_msg: (
                self._current_label.configure(text=m) if self.winfo_exists() else None
            ))

            if action.op_type == OpType.create_folder:
                success = True if self._dry_run else create_folder(action.destination)
                logger.log_folder(action.destination, success, dry_run=self._dry_run)
                tag = "done" if success else "fail"
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
                    if self._dry_run:
                        result = MoveResult(success=True,
                                             source_original=action.source,
                                             destination_final=action.destination)
                        logger.log_move(result, dry_run=True)
                    else:
                        result = move_file(action.source, action.destination)
                        logger.log_move(result)
                    if result.success:
                        ok_count += 1
                        tag = "done"
                        if result.is_duplicate:
                            dup_count += 1
                        if self._engine:
                            try:
                                self._engine.emit_event("move", True)
                            except Exception:
                                pass
                    else:
                        fail_count += 1
                        tag = "fail"
                        if self._engine:
                            try:
                                self._engine.emit_event("move", False)
                            except Exception:
                                pass

            iid = self._action_iid.get(i)
            if iid is not None:
                self.after(0, lambda id_=iid, t=tag: (
                    self._tree.item(id_, tags=(t,)) if self.winfo_exists() else None
                ))

            sc = theme.SUCCESS if fail_count == 0 else theme.WARNING
            dup_note = f"  ⧉ {dup_count} Duplikat(e)" if dup_count else ""
            msg = f"{ok_count} ✓  {fail_count} ✗{dup_note}  –  {i + 1}/{total}"
            self.after(0, lambda m=msg, c=sc: (
                self._result_label.configure(text=m, text_color=c)
                if self.winfo_exists() else None
            ))

        logger.close()
        log_path = logger.get_session_path()

        self.after(0, lambda: (
            self._current_label.configure(text="") if self.winfo_exists() else None
        ))
        fc = theme.SUCCESS if fail_count == 0 else theme.WARNING
        dup_note = f", {dup_count} Duplikat(e) nach _Duplikate/" if dup_count else ""
        fm = f"Abgeschlossen: {ok_count} erfolgreich, {fail_count} fehlgeschlagen{dup_note}."
        self.after(0, lambda: (
            self._result_label.configure(text=fm, text_color=fc) if self.winfo_exists() else None
        ))
        self.after(0, lambda: (
            self._exec_btn.configure(state="normal", text="✓  Nochmal") if self.winfo_exists() else None
        ))
        self.after(0, lambda: (
            self._cancel_btn.configure(state="normal", text="✗  Schließen") if self.winfo_exists() else None
        ))
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
                {"op_type": a.op_type.value,
                 "source":  str(a.source) if a.source else None,
                 "destination": str(a.destination),
                 "reason":  a.reason}
                for a in self._plan.actions
            ],
        }
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self._result_label.configure(text=f"Exportiert: {dest.name}",
                                      text_color=theme.ACCENT_DIM)
