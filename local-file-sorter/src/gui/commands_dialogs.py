"""Dialogs for saving and managing custom sort commands."""
from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from src.commands.manager import Command, CommandManager, make_slug
from src.gui import theme


class SaveCommandDialog(ctk.CTkToplevel):
    """Save the current prompt text as a named command."""

    def __init__(
        self,
        parent,
        cmd_mgr: CommandManager,
        prompt_text: str = "",
        recursive: bool = False,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._cmd_mgr  = cmd_mgr
        self._prompt   = prompt_text
        self._on_saved = on_saved

        self.title("Befehl speichern")
        self.geometry("480x290")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self.focus_set()
        self._build(recursive)

    # ------------------------------------------------------------------

    def _build(self, recursive: bool) -> None:
        ctk.CTkLabel(self, text="BEFEHL SPEICHERN", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED,
                     ).pack(anchor="w", padx=24, pady=(18, 10))

        self._name_var = self._row_entry("Name *", "")
        self._desc_var = self._row_entry("Beschreibung", "")

        rec_row = ctk.CTkFrame(self, fg_color="transparent")
        rec_row.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(rec_row, text="Recursive merken",
                     text_color=theme.TEXT, font=theme.FONT_BODY).pack(side="left")
        self._rec_var = ctk.BooleanVar(value=recursive)
        ctk.CTkCheckBox(rec_row, text="", variable=self._rec_var,
                        fg_color=theme.ACCENT_PRIMARY,
                        checkmark_color=theme.BG_DEEP).pack(side="right")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 12))
        ctk.CTkButton(btn_row, text="Speichern", width=120,
                      command=self._save, **theme.btn_primary()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Abbrechen", width=120,
                      command=self.destroy, **theme.btn_ghost()).pack(side="right")

    def _row_entry(self, label: str, default: str) -> ctk.StringVar:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=5)
        ctk.CTkLabel(row, text=label, width=130, anchor="w",
                     text_color=theme.TEXT_MUTED, font=theme.FONT_BODY).pack(side="left")
        var = ctk.StringVar(value=default)
        ctk.CTkEntry(row, textvariable=var, fg_color=theme.SURFACE,
                     border_color=theme.SURFACE_HI, text_color=theme.TEXT,
                     font=theme.FONT_MONO_SM).pack(side="left", fill="x", expand=True)
        return var

    def _save(self) -> None:
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Name fehlt", "Bitte einen Namen eingeben.", parent=self)
            return
        cmd = Command(
            name=name,
            description=self._desc_var.get().strip(),
            prompt_text=self._prompt,
            default_recursive=self._rec_var.get(),
        )
        try:
            self._cmd_mgr.save_command(cmd)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen:\n{exc}", parent=self)
            return
        if self._on_saved:
            self._on_saved()
        self.destroy()


# ---------------------------------------------------------------------------

class ManageCommandsDialog(ctk.CTkToplevel):
    """List, rename, and soft-delete saved commands."""

    def __init__(
        self,
        parent,
        cmd_mgr: CommandManager,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._cmd_mgr    = cmd_mgr
        self._on_changed = on_changed

        self.title("Befehle verwalten")
        self.geometry("660x480")
        self.minsize(500, 340)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self._build()
        self._load_list()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=44, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="BEFEHLE VERWALTEN", font=theme.FONT_MONO_BOLD,
                     text_color=theme.ACCENT_PRIMARY).pack(side="left", padx=16, pady=12)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE, corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        note = ctk.CTkLabel(self,
                            text="Löschen entfernt nur die Befehls-Vorlage, keine Nutzer-Dateien.",
                            font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED, anchor="w")
        note.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 2))

        ctk.CTkButton(self, text="Schließen", width=120,
                      command=self.destroy, **theme.btn_ghost(),
                      ).grid(row=3, column=0, sticky="e", padx=16, pady=(4, 12))

    def _load_list(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

        metas = self._cmd_mgr.list_commands()
        if not metas:
            ctk.CTkLabel(self._scroll, text="Keine gespeicherten Befehle.",
                         text_color=theme.TEXT_MUTED, font=theme.FONT_BODY,
                         ).grid(row=0, column=0, padx=16, pady=24)
            return

        for i, meta in enumerate(metas):
            self._add_row(i, meta)

    def _add_row(self, idx: int, meta) -> None:
        bg   = theme.SURFACE if idx % 2 == 0 else theme.SURFACE_HI
        card = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=4)
        card.grid(row=idx, column=0, sticky="ew", padx=8, pady=3)
        card.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(info, text=meta.name, font=theme.FONT_MONO_BOLD,
                     text_color=theme.TEXT, anchor="w").pack(anchor="w")
        if meta.description:
            ctk.CTkLabel(info, text=meta.description, font=theme.FONT_MONO_SM,
                         text_color=theme.TEXT_MUTED, anchor="w").pack(anchor="w")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=0, column=1, padx=8, pady=8)
        ctk.CTkButton(btns, text="Umbenennen", width=110,
                      command=lambda m=meta: self._rename(m),
                      **theme.btn_ghost()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="✗  Löschen", width=96,
                      command=lambda m=meta: self._delete(m),
                      **theme.btn_danger()).pack(side="left")

    # ------------------------------------------------------------------

    def _delete(self, meta) -> None:
        confirmed = messagebox.askyesno(
            title="Befehl löschen",
            message=(f'"{meta.name}" löschen?\n\n'
                     "Löscht nur die Befehls-Vorlage, keine Nutzer-Dateien."),
            parent=self,
        )
        if not confirmed:
            return
        self._cmd_mgr.delete_command_file(meta.slug)
        self._load_list()
        if self._on_changed:
            self._on_changed()

    def _rename(self, meta) -> None:
        dlg = _RenameDialog(self, meta.name)
        self.wait_window(dlg)
        new_name = getattr(dlg, "result", None)
        if not new_name or new_name == meta.name:
            return
        try:
            cmd = self._cmd_mgr.load_command(meta.slug)
            original_created = cmd.created_at
            cmd.name        = new_name
            cmd.created_at  = original_created
            self._cmd_mgr.save_command(cmd)
            if make_slug(new_name) != meta.slug:
                self._cmd_mgr.delete_command_file(meta.slug)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Umbenennen fehlgeschlagen:\n{exc}", parent=self)
            return
        self._load_list()
        if self._on_changed:
            self._on_changed()


# ---------------------------------------------------------------------------

class _RenameDialog(ctk.CTkToplevel):
    """Single-field input popup for renaming a command."""

    def __init__(self, parent, current_name: str) -> None:
        super().__init__(parent)
        self.result: str | None = None
        self.title("Befehl umbenennen")
        self.geometry("400x160")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_DEEP)
        self.grab_set()
        self.focus_set()
        self._build(current_name)

    def _build(self, current_name: str) -> None:
        ctk.CTkLabel(self, text="Neuer Name:", text_color=theme.TEXT_MUTED,
                     font=theme.FONT_BODY).pack(anchor="w", padx=20, pady=(16, 4))
        self._var = ctk.StringVar(value=current_name)
        entry = ctk.CTkEntry(self, textvariable=self._var,
                             fg_color=theme.SURFACE, border_color=theme.SURFACE_HI,
                             text_color=theme.TEXT, font=theme.FONT_MONO_SM)
        entry.pack(fill="x", padx=20)
        entry.select_range(0, "end")
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._confirm())

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(row, text="OK", width=90, command=self._confirm,
                      **theme.btn_primary()).pack(side="right", padx=(6, 0))
        ctk.CTkButton(row, text="Abbrechen", width=100,
                      command=self.destroy, **theme.btn_ghost()).pack(side="right")

    def _confirm(self) -> None:
        name = self._var.get().strip()
        if name:
            self.result = name
            self.destroy()
