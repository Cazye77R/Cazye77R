"""Search page: semantic, fulltext, hybrid, and tag-based search."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from ui.app_state import get_smart_search, get_vault_manager, get_note_assistant, init_session_state
from ui.components.note_card import tag_badge

init_session_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCORE_COLORS = {
    "high":   ("#a6e3a1", "#1e1e2e"),  # green text, dark bg
    "medium": ("#f9e2af", "#1e1e2e"),  # yellow
    "low":    ("#f38ba8", "#1e1e2e"),  # red
}


def _score_badge(score: float) -> str:
    if score >= 0.7:
        tier = "high"
        label = f"{score:.0%} ●"
    elif score >= 0.4:
        tier = "medium"
        label = f"{score:.0%} ◕"
    else:
        tier = "low"
        label = f"{score:.0%} ○"
    fg, bg = _SCORE_COLORS[tier]
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {fg};'
        f'border-radius:10px;padding:2px 8px;font-size:11px;font-weight:600;'
        f'margin-left:6px;">{label}</span>'
    )


def _highlight(text: str, query: str) -> str:
    ss = get_smart_search()
    if ss and query:
        try:
            return ss.highlight_matches(text, query)
        except Exception:
            pass
    return text


def _result_card(result, query: str) -> None:
    filename = result.filename if hasattr(result, "filename") else result.get("filename", "")
    title = result.title if hasattr(result, "title") else result.get("title", filename)
    excerpt = result.excerpt if hasattr(result, "excerpt") else result.get("excerpt", "")
    tags = result.tags if hasattr(result, "tags") else result.get("tags", [])
    score = result.score if hasattr(result, "score") else result.get("score", 0.0)
    match_type = result.match_type if hasattr(result, "match_type") else result.get("match_type", "")

    highlighted = _highlight(excerpt, query)
    tag_html = "".join(tag_badge(t) for t in tags[:6])
    score_html = _score_badge(score)
    type_label = {"semantic": "🔮 Semantisch", "fulltext": "📄 Volltext", "hybrid": "⚡ Hybrid", "tag": "🏷️ Tag"}.get(match_type, "")

    col_card, col_btn = st.columns([6, 1])
    with col_card:
        st.markdown(
            f'<div style="background:#313244;border:1.5px solid #45475a;border-radius:8px;'
            f'padding:12px 14px;margin-bottom:6px;">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">'
            f'<span style="font-weight:600;color:#cdd6f4;font-size:14px;">{title}</span>'
            f'{score_html}'
            f'<span style="margin-left:8px;color:#6c7086;font-size:11px;">{type_label}</span>'
            f'</div>'
            f'<div style="color:#a6adc8;font-size:12px;line-height:1.5;margin-bottom:6px;">{highlighted}</div>'
            f'<div>{tag_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("📖", key=f"open_{filename}_{score}", help="Notiz öffnen"):
            st.session_state["current_note"] = filename
            st.switch_page("pages/02_Notes.py")


def _suggest_similar(query: str) -> list[str]:
    assistant = get_note_assistant()
    if not assistant:
        return []
    try:
        prompt = (
            f'Schlage 4 ähnliche oder verwandte Suchanfragen für "{query}" vor. '
            f'Antworte nur mit einer JSON-Liste, z.B. ["Anfrage 1", "Anfrage 2"].'
        )
        raw = assistant._ollama.chat(
            [{"role": "user", "content": prompt}],
            system_prompt="Du bist ein Suchassistent. Antworte ausschließlich mit einer JSON-Liste.",
        )
        import json, re
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if m:
            return json.loads(m.group())[:4]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.markdown("<h1>🔍 Suche</h1>", unsafe_allow_html=True)

# ── Search bar ───────────────────────────────────────────────────────────────
query = st.text_input(
    "Suchanfrage",
    placeholder="Was möchtest du wissen? (z.B. 'Python async Grundlagen')",
    label_visibility="collapsed",
    key="search_query_input",
)

# ── Filter row ───────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns([1.5, 2, 1.5, 1.5])
with f1:
    mode = st.selectbox(
        "Modus",
        ["Hybrid", "Semantisch", "Volltext", "Tag"],
        label_visibility="collapsed",
        key="search_mode",
    )
with f2:
    try:
        from core.database import get_all_tags
        all_tags = [t for t, _ in get_all_tags()]
    except Exception:
        all_tags = []
    selected_tags = st.multiselect(
        "Tags filtern",
        all_tags,
        placeholder="Alle Tags",
        label_visibility="collapsed",
        key="search_tags",
    )
with f3:
    from datetime import date
    date_from = st.date_input("Von", value=None, label_visibility="collapsed", key="search_date_from")
with f4:
    date_to = st.date_input("Bis", value=None, label_visibility="collapsed", key="search_date_to")

st.divider()

# ── Execute search ───────────────────────────────────────────────────────────
if not query.strip():
    st.markdown(
        "<div style='text-align:center;padding:60px;color:#6c7086;'>"
        "<div style='font-size:48px;'>🔍</div>"
        "<p>Gib oben einen Suchbegriff ein.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

mode_map = {"Hybrid": "hybrid", "Semantisch": "semantic", "Volltext": "fulltext", "Tag": "tag"}
search_mode = mode_map.get(mode, "hybrid")

col_results, col_sidebar = st.columns([3, 1])

with col_results:
    st.markdown(f"**Ergebnisse für:** `{query}`")

    ss = get_smart_search()
    results = []

    if ss:
        with st.spinner("Suche…"):
            try:
                raw_results = ss.search(query, mode=search_mode)
                results = list(raw_results)
            except Exception as exc:
                st.warning(f"Suchfehler: {exc}")
    else:
        # Fallback: fulltext via vault manager
        vm = get_vault_manager()
        try:
            notes = vm.search_notes_fulltext(query)
            from plugins.smart_search import SearchResult
            results = [
                SearchResult(
                    filename=n["filename"],
                    title=n["title"],
                    excerpt=n.get("content", "")[:300],
                    tags=n.get("tags", []),
                    score=0.5,
                    match_type="fulltext",
                )
                for n in notes
            ]
        except Exception as exc:
            st.warning(f"Fallback-Suchfehler: {exc}")

    # Tag filter
    if selected_tags:
        results = [
            r for r in results
            if any(t in (r.tags if hasattr(r, "tags") else r.get("tags", [])) for t in selected_tags)
        ]

    # Date filter
    if date_from or date_to:
        from datetime import datetime
        filtered = []
        vm2 = get_vault_manager()
        for r in results:
            fn = r.filename if hasattr(r, "filename") else r.get("filename", "")
            note = vm2.get_note(fn)
            if note:
                mod = note.get("modified_at")
                if isinstance(mod, datetime):
                    mod_date = mod.date()
                elif isinstance(mod, str) and mod:
                    try:
                        mod_date = datetime.fromisoformat(mod[:10]).date()
                    except Exception:
                        mod_date = None
                else:
                    mod_date = None
                if mod_date:
                    if date_from and mod_date < date_from:
                        continue
                    if date_to and mod_date > date_to:
                        continue
            filtered.append(r)
        results = filtered

    if not results:
        st.info(f'Keine Ergebnisse für „{query}" gefunden.')
        st.markdown("---")
        st.markdown("**Möchtest du eine neue Notiz zu diesem Thema erstellen?**")
        if st.button("➕ Neue Notiz erstellen", type="primary"):
            st.session_state["new_note_title_prefill"] = query
            st.switch_page("pages/02_Notes.py")
    else:
        st.markdown(f"<p style='color:#6c7086;font-size:12px;'>{len(results)} Treffer</p>", unsafe_allow_html=True)
        for r in results:
            _result_card(r, query)

with col_sidebar:
    st.markdown("**💡 Ähnliche Anfragen**")
    if "similar_queries" not in st.session_state or st.session_state.get("_last_sq") != query:
        st.session_state["similar_queries"] = []
        st.session_state["_last_sq"] = query

    if not st.session_state["similar_queries"]:
        if st.button("Vorschläge laden", key="load_similar", use_container_width=True):
            with st.spinner("Lade…"):
                st.session_state["similar_queries"] = _suggest_similar(query)
                st.rerun()
    else:
        for sq in st.session_state["similar_queries"]:
            if st.button(f"🔎 {sq}", key=f"sq_{sq}", use_container_width=True):
                st.session_state["search_query_input"] = sq
                st.rerun()

    st.divider()
    st.markdown("**🔍 Suchtipps**")
    st.markdown(
        "<ul style='color:#6c7086;font-size:12px;padding-left:16px;'>"
        "<li><b>Hybrid</b>: Kombination aus semantisch + Volltext</li>"
        "<li><b>Semantisch</b>: Bedeutungsbasiert via KI</li>"
        "<li><b>Volltext</b>: Exakte Wortsuche</li>"
        "<li><b>Tag</b>: Suche nach Tag-Namen</li>"
        "</ul>",
        unsafe_allow_html=True,
    )
