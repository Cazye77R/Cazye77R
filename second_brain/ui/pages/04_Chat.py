"""Chat page: RAG-backed conversational interface with streaming."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from ui.app_state import get_rag_engine, get_vault_manager, init_session_state

init_session_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_chips(sources: list[dict]) -> str:
    if not sources:
        return ""
    chips = "".join(
        f'<span style="background:#313244;color:#89b4fa;border:1px solid #89b4fa;'
        f'border-radius:10px;padding:2px 9px;font-size:11px;margin-right:4px;">'
        f'[[{s["title"]}]]</span>'
        for s in sources[:5]
    )
    return f'<div style="margin-top:6px;">{chips}</div>'


def _render_message(role: str, content: str, sources: list[dict] | None = None) -> None:
    is_user = role == "user"
    bg = "#45475a" if is_user else "#313244"
    align = "flex-end" if is_user else "flex-start"
    name = "Du" if is_user else "🤖 Assistent"
    name_color = "#cdd6f4" if is_user else "#89b4fa"

    src_html = _source_chips(sources or [])
    content_escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

    st.markdown(
        f'<div style="display:flex;flex-direction:column;align-items:{align};margin-bottom:12px;">'
        f'<span style="font-size:11px;color:#6c7086;margin-bottom:3px;">{name}</span>'
        f'<div style="background:{bg};border-radius:12px;padding:10px 14px;max-width:80%;'
        f'color:#cdd6f4;font-size:14px;line-height:1.5;">'
        f'{content_escaped}{src_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _streaming_answer(question: str) -> tuple[str, list[dict]]:
    """Ask RAG engine, stream response, return (full_answer, sources)."""
    rag = get_rag_engine()
    if not rag:
        return "KI-Engine nicht verfügbar. Starte Ollama und lade die Seite neu.", []

    try:
        context_notes = rag.search_semantic(question, n_results=5)
        sources: list[dict] = []
        context_parts: list[str] = []
        seen: set[str] = set()
        vm = get_vault_manager()
        for r in context_notes[:5]:
            fn = r["filename"]
            if fn in seen:
                continue
            seen.add(fn)
            note = vm.get_note(fn)
            if note:
                context_parts.append(f"## {note['title']}\n{note['content'][:1500]}")
                sources.append({"filename": fn, "title": note["title"]})

        context = "\n\n---\n\n".join(context_parts) or "Keine relevanten Notizen gefunden."

        messages = [
            {
                "role": "user",
                "content": (
                    f"Kontext aus meinen Notizen:\n\n{context}\n\n"
                    f"Frage: {question}"
                ),
            }
        ]

        _SYSTEM = (
            "Du bist ein persönlicher Wissensassistent. "
            "Antworte NUR basierend auf den gegebenen Notizen. "
            "Wenn die Antwort nicht in den Notizen steht, sage das klar. "
            "Antworte auf Deutsch und sei präzise."
        )

        from ai.ollama_client import OllamaClient, OllamaConnectionError

        client = OllamaClient()
        full_answer = ""

        placeholder = st.empty()
        streamed = ""

        try:
            for chunk in client.chat_stream(messages, system_prompt=_SYSTEM):
                streamed += chunk
                placeholder.markdown(
                    f'<div style="background:#313244;border-radius:12px;padding:10px 14px;'
                    f'color:#cdd6f4;font-size:14px;line-height:1.5;">{streamed}▋</div>',
                    unsafe_allow_html=True,
                )
            full_answer = streamed
            placeholder.empty()
        except OllamaConnectionError:
            placeholder.empty()
            full_answer = rag.answer_question(question, context_notes).get("answer", "")

        return full_answer, sources

    except Exception as exc:
        return f"Fehler beim Antworten: {exc}", []


def _save_chat_as_note() -> None:
    history = st.session_state.get("chat_history", [])
    if not history:
        return
    lines = ["# Chat-Zusammenfassung\n"]
    for msg in history:
        role_label = "**Du:**" if msg["role"] == "user" else "**Assistent:**"
        lines.append(f"{role_label}\n{msg['content']}\n")
    content = "\n".join(lines)
    try:
        vm = get_vault_manager()
        from datetime import datetime
        title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        note = vm.create_note(title, content, tags=["chat", "ki"])
        st.session_state["current_note"] = note["filename"]
        st.success(f'Gespeichert als „{title}“')
        from ui.app_state import refresh_vault_stats
        refresh_vault_stats()
    except Exception as exc:
        st.error(f"Fehler beim Speichern: {exc}")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.markdown("<h1>💬 Chat</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#6c7086;'>Stelle Fragen zu deinem Vault – der Assistent antwortet "
    "basierend auf deinen Notizen.</p>",
    unsafe_allow_html=True,
)

# Toolbar
tb1, tb2, _ = st.columns([1, 1, 4])
with tb1:
    if st.button("🗑 Chat leeren", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()
with tb2:
    if st.button("💾 Als Notiz", use_container_width=True):
        _save_chat_as_note()

st.divider()

# Chat history display
history: list[dict] = st.session_state.get("chat_history", [])

if not history:
    st.markdown(
        "<div style='text-align:center;padding:40px;color:#6c7086;'>"
        "<div style='font-size:40px;'>💬</div>"
        "<p>Starte ein Gespräch, indem du unten eine Frage eingibst.</p>"
        "<p style='font-size:12px;'>Der Assistent durchsucht deine Notizen und antwortet kontextbezogen.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    for msg in history:
        _render_message(msg["role"], msg["content"], msg.get("sources"))

st.divider()

# Input area
with st.form("chat_input_form", clear_on_submit=True):
    user_input = st.text_area(
        "Deine Frage",
        placeholder="Was möchtest du über deine Notizen wissen?",
        label_visibility="collapsed",
        height=80,
        key="chat_user_input",
    )
    submitted = st.form_submit_button("📤 Senden", type="primary", use_container_width=True)

if submitted and user_input.strip():
    # Append user message
    history.append({"role": "user", "content": user_input.strip(), "sources": []})
    st.session_state["chat_history"] = history

    # Generate streamed answer
    with st.spinner(""):
        answer, sources = _streaming_answer(user_input.strip())

    history.append({"role": "assistant", "content": answer, "sources": sources})
    st.session_state["chat_history"] = history
    st.rerun()

# Source navigation at bottom (if last reply has sources)
if history and history[-1]["role"] == "assistant":
    last_sources = history[-1].get("sources", [])
    if last_sources:
        st.markdown("**📎 Quellen der letzten Antwort:**")
        src_cols = st.columns(min(len(last_sources), 4))
        for i, src in enumerate(last_sources[:4]):
            with src_cols[i]:
                if st.button(f"→ {src['title']}", key=f"src_nav_{src['filename']}_{i}", use_container_width=True):
                    st.session_state["current_note"] = src["filename"]
                    st.switch_page("pages/02_Notes.py")
