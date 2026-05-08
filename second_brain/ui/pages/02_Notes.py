"""Notes page: list, view, edit, create, and AI-assisted tools."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from ui.app_state import (
    get_note_assistant,
    get_vault_manager,
    init_session_state,
    invalidate_data_caches,
    refresh_vault_stats,
    render_ollama_warning,
)
from ui.components.note_card import tag_badge

init_session_state()

# ---------------------------------------------------------------------------
# Helper: New-note dialog
# ---------------------------------------------------------------------------

@st.dialog("📝 Neue Notiz erstellen")
def _new_note_dialog() -> None:
    title = st.text_input("Titel *", placeholder="Mein neues Konzept")
    content = st.text_area("Startinhalt (optional)", height=180, placeholder="# Einstieg\n\n...")
    tags_raw = st.text_input("Tags (kommagetrennt)", placeholder="ki, python, ideen")

    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("✅ Erstellen", type="primary", use_container_width=True):
            if not title.strip():
                st.error("Titel ist erforderlich.")
            else:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                try:
                    vm = get_vault_manager()
                    note = vm.create_note(title.strip(), content, tags)
                    st.session_state["current_note"] = note["filename"]
                    refresh_vault_stats()
                    st.toast(f"Notiz \"{title.strip()}\" erstellt!", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fehler: {exc}")
    with col_cancel:
        if st.button("❌ Abbrechen", use_container_width=True):
            st.rerun()


# ---------------------------------------------------------------------------
# Helper: sort + filter notes
# ---------------------------------------------------------------------------

def _get_sorted_notes(vm, search: str, sort_by: str) -> list[dict]:
    notes = vm.get_all_notes()
    if search:
        q = search.lower()
        notes = [n for n in notes if q in n["title"].lower() or q in n.get("content", "").lower()]
    if sort_by == "Name":
        notes.sort(key=lambda n: n["title"].lower())
    elif sort_by == "Datum":
        notes.sort(key=lambda n: n.get("modified_at") or datetime.min, reverse=True)
    elif sort_by == "Wörter":
        notes.sort(key=lambda n: n.get("word_count", 0), reverse=True)
    return notes


# ---------------------------------------------------------------------------
# Helper: render note viewer
# ---------------------------------------------------------------------------

def _render_note_viewer(note: dict) -> None:
    from core.markdown_parser import render_markdown
    from core.vault_manager import VaultManager

    title = note.get("title", "")
    tags = note.get("tags", [])
    wikilinks = note.get("wikilinks", [])
    word_count = note.get("word_count", 0)
    modified = note.get("modified_at", "")

    # Title bar
    st.markdown(f"<h2 style='margin-bottom:4px;'>{title}</h2>", unsafe_allow_html=True)

    # Metadata row
    meta_parts = [f"📝 {word_count} Wörter"]
    if isinstance(modified, datetime):
        meta_parts.append(f"🕐 {modified.strftime('%d.%m.%Y %H:%M')}")
    st.markdown(
        f"<p style='color:#6c7086;font-size:12px;'>{' &nbsp;·&nbsp; '.join(meta_parts)}</p>",
        unsafe_allow_html=True,
    )

    # Tags
    if tags:
        badges = "".join(tag_badge(t) for t in tags)
        st.markdown(f"<div style='margin-bottom:12px;'>{badges}</div>", unsafe_allow_html=True)

    st.divider()

    # Rendered content
    html = render_markdown(note.get("raw_text", ""))
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # Backlinks
    vm = get_vault_manager()
    backlinks = vm.get_backlinks(note["filename"])
    if backlinks:
        st.markdown("#### 🔙 Backlinks")
        for bl in backlinks:
            if st.button(
                f"← {bl['title']}",
                key=f"bl_{bl['filename']}",
                use_container_width=False,
            ):
                st.session_state["current_note"] = bl["filename"]
                st.rerun()
    else:
        st.markdown(
            "<p style='color:#6c7086;font-size:12px;'>Keine Backlinks.</p>",
            unsafe_allow_html=True,
        )

    # Wikilinks section
    if wikilinks:
        st.markdown("#### 🔗 Links in dieser Notiz")
        link_cols = st.columns(min(len(wikilinks), 4))
        for i, link in enumerate(wikilinks[:8]):
            with link_cols[i % len(link_cols)]:
                target_file = f"{link}.md"
                if st.button(f"→ {link}", key=f"wl_{link}_{i}", use_container_width=True):
                    st.session_state["current_note"] = target_file
                    st.rerun()


# ---------------------------------------------------------------------------
# Helper: render note editor
# ---------------------------------------------------------------------------

def _render_note_editor(note: dict) -> None:
    filename = note["filename"]
    content = note.get("content", "")

    # Keyboard shortcut hint
    st.markdown(
        "<p style='color:#6c7086;font-size:11px;margin-bottom:4px;'>"
        "💾 Tipp: Klicke <b>Speichern</b> oder drücke <b>Ctrl+Enter</b> im Textfeld</p>",
        unsafe_allow_html=True,
    )

    new_content = st.text_area(
        "Inhalt bearbeiten",
        value=content,
        height=480,
        key=f"editor_{filename}",
        label_visibility="collapsed",
    )

    # Dirty tracking – detect unsaved changes
    saved_content = st.session_state.get("_editor_saved_content", content)
    is_dirty = new_content != saved_content
    if is_dirty:
        st.markdown(
            "<p style='color:#f9e2af;font-size:11px;margin:0;'>⚠️ Ungespeicherte Änderungen</p>",
            unsafe_allow_html=True,
        )

    save_col, cancel_col, _ = st.columns([1, 1, 4])
    with save_col:
        if st.button("💾 Speichern", type="primary", use_container_width=True):
            try:
                vm = get_vault_manager()
                vm.update_note(filename, new_content)
                from core.database import upsert_note
                updated = vm.get_note(filename)
                if updated:
                    upsert_note(updated)
                invalidate_data_caches()
                refresh_vault_stats()
                st.session_state["note_edit_mode"] = False
                st.session_state["_editor_saved_content"] = new_content
                st.session_state["_editor_dirty"] = False
                st.toast("Gespeichert!", icon="💾")
                st.rerun()
            except Exception as exc:
                st.error(f"Speicherfehler: {exc}")
    with cancel_col:
        if st.button("✖ Abbrechen", use_container_width=True):
            st.session_state["note_edit_mode"] = False
            st.session_state["_editor_dirty"] = False
            st.rerun()


# ---------------------------------------------------------------------------
# Helper: AI actions panel
# ---------------------------------------------------------------------------

def _render_ai_panel(note: dict) -> None:
    assistant = get_note_assistant()
    if not assistant:
        st.caption("KI nicht verfügbar.")
        return

    content = note.get("content", "")

    st.markdown("##### 🏷️ Tags vorschlagen")
    if st.button("Tags analysieren", key="ai_tags", use_container_width=True):
        with st.spinner("Analysiere…"):
            try:
                vm = get_vault_manager()
                all_tags = [t for t, _ in __import__("core.database", fromlist=["get_all_tags"]).get_all_tags()]
                st.session_state["ai_tags"] = assistant.suggest_tags(content, all_tags)
            except Exception as exc:
                st.warning(f"Fehler: {exc}")

    if st.session_state.get("ai_tags"):
        tags_html = "".join(tag_badge(t) for t in st.session_state["ai_tags"])
        st.markdown(tags_html, unsafe_allow_html=True)

    st.markdown("##### 🔗 Links vorschlagen")
    if st.button("Links suchen", key="ai_links", use_container_width=True):
        with st.spinner("Suche ähnliche Notizen…"):
            try:
                vm = get_vault_manager()
                titles = [n["title"] for n in vm.get_all_notes()]
                st.session_state["ai_links"] = assistant.suggest_links(content, titles)
            except Exception as exc:
                st.warning(f"Fehler: {exc}")

    if st.session_state.get("ai_links"):
        for lnk in st.session_state["ai_links"][:5]:
            conf = lnk.get("confidence", 0)
            bar = "█" * int(conf * 10)
            st.markdown(
                f'<div style="background:#313244;border-radius:6px;padding:6px 10px;margin-bottom:4px;">'
                f'<span style="color:#cdd6f4;font-size:13px;">[[{lnk["title"]}]]</span><br>'
                f'<span style="color:#a6adc8;font-size:11px;">{lnk.get("reason","")}</span><br>'
                f'<span style="color:#89b4fa;font-size:11px;">{bar} {conf:.0%}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("##### ✨ Notiz strukturieren")
    if st.button("Struktur vorschlagen", key="ai_struct", use_container_width=True):
        with st.spinner("Strukturiere…"):
            try:
                result = assistant.structure_note(content)
                st.session_state["ai_structure"] = result
            except Exception as exc:
                st.warning(f"Fehler: {exc}")

    if st.session_state.get("ai_structure"):
        with st.expander("Strukturierter Vorschlag", expanded=True):
            st.markdown(st.session_state["ai_structure"])
            if st.button("✅ Übernehmen", key="ai_struct_apply"):
                try:
                    vm = get_vault_manager()
                    vm.update_note(note["filename"], st.session_state["ai_structure"])
                    st.session_state["ai_structure"] = ""
                    st.success("Übernommen!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fehler: {exc}")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.markdown("<h1>📝 Notizen</h1>", unsafe_allow_html=True)
render_ollama_warning()

vm = get_vault_manager()

# Three-column layout: note list | note content | AI actions
col_list, col_content, col_ai = st.columns([1, 3, 1.3])

# ── Note list (left) ─────────────────────────────────────────────────────────
with col_list:
    st.markdown("**📚 Notizen**")

    search_query = st.text_input(
        "🔍", placeholder="Suchen…", label_visibility="collapsed", key="note_search"
    )
    sort_by = st.selectbox(
        "Sortierung", ["Datum", "Name", "Wörter"], label_visibility="collapsed", key="note_sort"
    )

    if st.button("➕ Neue Notiz", type="primary", use_container_width=True):
        _new_note_dialog()

    st.divider()

    try:
        notes = _get_sorted_notes(vm, search_query, sort_by)
    except Exception:
        notes = []

    if not notes:
        st.caption("Keine Notizen gefunden.")
    else:
        current = st.session_state.get("current_note")
        for note in notes:
            is_sel = note["filename"] == current
            label = ("▶ " if is_sel else "") + note["title"]
            btn_type = "primary" if is_sel else "secondary"
            if st.button(
                label,
                key=f"list_{note['filename']}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state["current_note"] = note["filename"]
                st.session_state["note_edit_mode"] = False
                st.session_state["ai_tags"] = []
                st.session_state["ai_links"] = []
                st.session_state["ai_structure"] = ""
                st.session_state["_editor_saved_content"] = note.get("content", "")
                st.session_state["_editor_dirty"] = False
                st.rerun()

# ── Note content (center) ─────────────────────────────────────────────────────
with col_content:
    current_filename = st.session_state.get("current_note")

    if not current_filename:
        st.markdown(
            "<div style='text-align:center;padding:60px;color:#6c7086;'>"
            "<div style='font-size:48px;'>📄</div>"
            "<p>Wähle links eine Notiz aus oder erstelle eine neue.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        note = vm.get_note(current_filename)
        if not note:
            st.warning(f"Notiz '{current_filename}' nicht gefunden.")
            st.session_state["current_note"] = None
        else:
            # Mode toggle
            edit_mode = st.session_state.get("note_edit_mode", False)
            toggle_col, del_col, _ = st.columns([1, 1, 5])
            with toggle_col:
                mode_label = "👁 Ansehen" if edit_mode else "✏️ Bearbeiten"
                if st.button(mode_label, use_container_width=True):
                    st.session_state["note_edit_mode"] = not edit_mode
                    st.rerun()
            with del_col:
                if st.button("🗑 Löschen", use_container_width=True):
                    st.session_state["_confirm_delete"] = True

            # Delete confirmation
            if st.session_state.get("_confirm_delete"):
                st.warning(f"Notiz **{note['title']}** wirklich löschen?")
                yes_col, no_col, _ = st.columns([1, 1, 4])
                with yes_col:
                    if st.button("✅ Ja, löschen", type="primary"):
                        deleted_title = note.get("title", current_filename)
                        vm.delete_note(current_filename)
                        try:
                            from core.database import delete_note_from_db
                            delete_note_from_db(current_filename)
                        except Exception:
                            pass
                        invalidate_data_caches()
                        refresh_vault_stats()
                        st.session_state["current_note"] = None
                        st.session_state["_confirm_delete"] = False
                        st.toast(f'"{deleted_title}" gelöscht', icon="🗑️")
                        st.rerun()
                with no_col:
                    if st.button("❌ Abbrechen"):
                        st.session_state["_confirm_delete"] = False
                        st.rerun()

            st.divider()

            if edit_mode:
                _render_note_editor(note)
            else:
                _render_note_viewer(note)

# ── AI actions (right) ───────────────────────────────────────────────────────
with col_ai:
    st.markdown("**🤖 KI-Aktionen**")
    current_filename = st.session_state.get("current_note")
    if not current_filename:
        st.caption("Wähle eine Notiz aus.")
    else:
        note = vm.get_note(current_filename)
        if note:
            _render_ai_panel(note)
