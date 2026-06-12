"""Elephant – Streamlit frontend."""
import uuid
from pathlib import Path

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
API = "http://localhost:8000"
OLLAMA = "http://localhost:11434"
CATEGORIES = ("general", "projects", "conversations")
CAT_ICON = {"general": "📌", "projects": "🛠️", "conversations": "💬"}


# ─────────────────────────────────────────────────────────────────────────────
# API layer  –  raise on HTTP error, callers catch
# ─────────────────────────────────────────────────────────────────────────────
def _req(method: str, path: str, **kwargs) -> requests.Response:
    timeout = kwargs.pop("timeout", 30)
    r = requests.request(method, f"{API}{path}", timeout=timeout, **kwargs)
    r.raise_for_status()
    return r


def memories_list() -> list[dict]:
    try:
        return _req("GET", "/memories").json()
    except Exception:
        return []


def memories_create(category: str, title: str, content: str,
                    tags: list[str], importance: float) -> dict:
    return _req("POST", "/memories", json={
        "category": category, "title": title, "content": content,
        "tags": tags, "importance": importance,
    }).json()


def memories_update(filepath: str, content: str | None = None,
                    tags: list[str] | None = None, importance: float | None = None) -> dict:
    payload = {}
    if content is not None:
        payload["content"] = content
    if tags is not None:
        payload["tags"] = tags
    if importance is not None:
        payload["importance"] = importance
    return _req("PATCH", f"/memories/{filepath}", json=payload).json()


def memories_delete(filepath: str) -> None:
    _req("DELETE", f"/memories/{filepath}", timeout=10)


def memories_embed(filepath: str) -> dict:
    return _req("POST", "/memories/embed", json={"filepath": filepath}).json()


def memories_sync() -> dict:
    return _req("POST", "/memories/sync", timeout=60).json()


def chat_send(message: str, session_id: str, model: str | None = None) -> dict:
    return _req("POST", "/chat",
                json={"message": message, "session_id": session_id, "model": model},
                timeout=120).json()


def session_close(session_id: str) -> None:
    _req("POST", f"/sessions/{session_id}/close")


def ollama_models() -> list[str]:
    try:
        data = requests.get(f"{OLLAMA}/api/tags", timeout=3).json()
        return [m["name"] for m in data.get("models", [])] or ["llama3.1"]
    except Exception:
        return ["llama3.1", "mistral", "qwen2.5"]


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "sessions": [],     # list[str]
    "active": None,     # str | None
    "messages": {},     # {sid: [{role, content, sources}]}
    "model": "llama3.1",
    "edit_mem": None,   # dict | None — memory open in editor
    "flash": None,      # (level, text) | None
}


def _init() -> None:
    for k, v in _DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _flash(level: str, text: str) -> None:
    st.session_state.flash = (level, text)


def _pop_flash() -> None:
    if st.session_state.flash:
        lvl, txt = st.session_state.flash
        getattr(st, lvl)(txt)
        st.session_state.flash = None


# ─────────────────────────────────────────────────────────────────────────────
# Shared widgets
# ─────────────────────────────────────────────────────────────────────────────
def _score_bar(score: float, width: int = 5) -> str:
    n = round(max(0.0, min(1.0, score)) * width)
    return "█" * n + "░" * (width - n)


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"📎 {len(sources)} Quellen", expanded=False):
        for i, s in enumerate(sources):
            title = s.get("title") or Path(s["source_file"]).stem
            bar = _score_bar(s["score"])
            chunk = s["chunk"]
            st.markdown(
                f"**{title}** &nbsp; `{bar}` {s['score']:.2f}\n\n"
                f"> {chunk[:300]}{'…' if len(chunk) > 300 else ''}"
            )
            if i < len(sources) - 1:
                st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def _sidebar(memories: list[dict]) -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown("## 🐘 Elephant")
        st.divider()

        # ── Sessions ──────────────────────────────────────────────────────────
        if st.button("＋ Neue Session", use_container_width=True, type="primary"):
            sid = uuid.uuid4().hex[:8]
            ss.sessions.append(sid)
            ss.messages[sid] = []
            ss.active = sid
            st.rerun()

        if ss.sessions:
            st.caption("SESSIONS")
            for sid in list(ss.sessions):
                is_active = sid == ss.active
                c1, c2 = st.columns([5, 1])
                with c1:
                    label = f"**▶ {sid}**" if is_active else sid
                    if st.button(label, key=f"sel_{sid}", use_container_width=True):
                        ss.active = sid
                        st.rerun()
                with c2:
                    if st.button("✕", key=f"cls_{sid}"):
                        try:
                            session_close(sid)
                        except Exception:
                            pass
                        ss.sessions.remove(sid)
                        if ss.active == sid:
                            ss.active = ss.sessions[-1] if ss.sessions else None
                        st.rerun()

        st.divider()

        # ── Memory browser ────────────────────────────────────────────────────
        with st.expander("🗂️ Memory Browser"):
            if not memories:
                st.caption("Keine Memories vorhanden.")
            else:
                by_cat: dict[str, list] = {}
                for m in memories:
                    by_cat.setdefault(m["category"], []).append(m)

                for cat in CATEGORIES:
                    items = by_cat.get(cat, [])
                    if not items:
                        continue
                    st.markdown(f"**{CAT_ICON[cat]} {cat}** `{len(items)}`")
                    for m in items:
                        title = m["metadata"]["title"]
                        imp = float(m["metadata"]["importance"])
                        c1, c2 = st.columns([6, 1])
                        with c1:
                            if st.button(
                                f"`{_score_bar(imp)}` {title}",
                                key=f"view_{m['filepath']}",
                                use_container_width=True,
                                help=f"importance {imp:.2f} · {m['category']}",
                            ):
                                ss.edit_mem = m
                                st.rerun()
                        with c2:
                            if st.button("🗑️", key=f"del_{m['filepath']}"):
                                try:
                                    memories_delete(m["filepath"])
                                    _flash("success", f"Memory «{title}» gelöscht.")
                                except Exception as exc:
                                    _flash("error", str(exc))
                                st.rerun()

        # ── Sync ─────────────────────────────────────────────────────────────
        if st.button("🔄 Sync Memories", use_container_width=True):
            with st.spinner("Syncing…"):
                try:
                    r = memories_sync()
                    _flash("success", f"Sync: {r['synced']} neu, {r['skipped']} unverändert.")
                except Exception as exc:
                    _flash("error", str(exc))
            st.rerun()

        # ── Model selector ────────────────────────────────────────────────────
        st.divider()
        st.caption("MODELL")
        models = ollama_models()
        cur = ss.model
        idx = models.index(cur) if cur in models else 0
        selected = st.selectbox("", models, index=idx, label_visibility="collapsed")
        if selected != ss.model:
            ss.model = selected

        # ── Footer ────────────────────────────────────────────────────────────
        st.divider()
        n = len(memories)
        st.caption(f"🧠 {n} Erinnerung{'en' if n != 1 else ''} gespeichert")


# ─────────────────────────────────────────────────────────────────────────────
# Chat tab
# ─────────────────────────────────────────────────────────────────────────────
def _chat_tab() -> None:
    ss = st.session_state
    if ss.active is None:
        st.info("Erstelle eine neue Session über die Sidebar.")
        return

    msgs: list[dict] = ss.messages.get(ss.active, [])

    # Render conversation history
    for m in msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant":
                _render_sources(m.get("sources", []))

    # Handle new input
    if prompt := st.chat_input("Nachricht eingeben…"):
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(""):
                try:
                    data = chat_send(prompt, ss.active, ss.model)
                    reply = data["response"]
                    sources = data.get("sources", [])
                except Exception as exc:
                    reply = f"_Fehler beim Verbinden mit dem Backend: {exc}_"
                    sources = []
            st.markdown(reply)
            _render_sources(sources)

        msgs.append({"role": "user", "content": prompt, "sources": []})
        msgs.append({"role": "assistant", "content": reply, "sources": sources})
        ss.messages[ss.active] = msgs

        if len(msgs) >= 4:
            st.caption("🧠 Erinnerungen werden im Hintergrund extrahiert…")


# ─────────────────────────────────────────────────────────────────────────────
# Memory editor tab
# ─────────────────────────────────────────────────────────────────────────────
def _editor_tab() -> None:
    ss = st.session_state
    edit_t, new_t, import_t = st.tabs(["✏️ Bearbeiten", "➕ Neue Memory", "📥 Importieren"])

    # ── Edit existing ─────────────────────────────────────────────────────────
    with edit_t:
        m = ss.edit_mem
        if m is None:
            st.info("Wähle eine Memory aus dem **Memory Browser** in der Sidebar.")
        else:
            meta = m["metadata"]
            st.caption(f"`{m['filepath']}`")

            new_content = st.text_area(
                "Inhalt", value=m["content"], height=320, key="edit_content"
            )
            col_a, col_b = st.columns(2)
            with col_a:
                tags_raw = st.text_input(
                    "Tags (kommagetrennt)",
                    value=", ".join(meta.get("tags", [])),
                    key="edit_tags",
                )
            with col_b:
                new_imp = st.slider(
                    "Wichtigkeit", 0.0, 1.0, float(meta["importance"]), 0.05,
                    key="edit_imp",
                )

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("💾 Speichern", use_container_width=True, type="primary"):
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                    try:
                        memories_update(m["filepath"],
                                        content=new_content, tags=tags, importance=new_imp)
                        _flash("success", "💾 Memory aktualisiert.")
                    except Exception as exc:
                        _flash("error", str(exc))
                    st.rerun()
            with b2:
                if st.button("🔗 Embedden", use_container_width=True):
                    try:
                        r = memories_embed(m["filepath"])
                        _flash("success", f"Eingebettet: {r['chunks']} Chunks.")
                    except Exception as exc:
                        _flash("error", str(exc))
                    st.rerun()
            with b3:
                if st.button("✕ Schließen", use_container_width=True):
                    ss.edit_mem = None
                    st.rerun()

    # ── Create new ────────────────────────────────────────────────────────────
    with new_t:
        with st.form("new_memory_form"):
            n_title = st.text_input("Titel *")
            n_cat = st.selectbox("Kategorie", CATEGORIES)
            n_tags_raw = st.text_input("Tags (kommagetrennt)")
            n_imp = st.slider("Wichtigkeit", 0.0, 1.0, 0.5, 0.05)
            n_content = st.text_area("Inhalt (Markdown) *", height=260)
            submitted = st.form_submit_button(
                "💾 Speichern & einbetten", type="primary", use_container_width=True
            )

        if submitted:
            if not n_title.strip() or not n_content.strip():
                st.warning("Titel und Inhalt sind Pflichtfelder.")
            else:
                tags = [t.strip() for t in n_tags_raw.split(",") if t.strip()]
                try:
                    r = memories_create(n_cat, n_title, n_content, tags, n_imp)
                    memories_embed(r["filepath"])
                    _flash("success", f"💾 Memory gespeichert: «{n_title}»")
                except Exception as exc:
                    _flash("error", str(exc))
                st.rerun()

    # ── Import markdown ───────────────────────────────────────────────────────
    with import_t:
        st.caption("Lade eine `.md`-Datei hoch. Der Dateiname wird als Titel verwendet.")
        with st.form("import_form"):
            i_cat = st.selectbox("Kategorie", CATEGORIES, key="import_cat")
            i_imp = st.slider("Wichtigkeit", 0.0, 1.0, 0.5, 0.05, key="import_imp")
            uploaded = st.file_uploader("Markdown-Datei wählen", type=["md"])
            do_import = st.form_submit_button(
                "📥 Importieren", type="primary", use_container_width=True
            )

        if do_import:
            if uploaded is None:
                st.warning("Bitte eine Datei auswählen.")
            else:
                title = Path(uploaded.name).stem
                content = uploaded.read().decode("utf-8", errors="replace")
                try:
                    r = memories_create(i_cat, title, content, [], i_imp)
                    memories_embed(r["filepath"])
                    _flash("success", f"📥 Importiert & eingebettet: «{title}»")
                except Exception as exc:
                    _flash("error", str(exc))
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="Elephant",
        page_icon="🐘",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init()

    memories = memories_list()

    _sidebar(memories)
    _pop_flash()

    chat_tab, editor_tab = st.tabs(["💬 Chat", "📝 Memory Editor"])
    with chat_tab:
        _chat_tab()
    with editor_tab:
        _editor_tab()


if __name__ == "__main__":
    main()
