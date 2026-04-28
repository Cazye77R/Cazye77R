"""Dashboard page: stats, recent notes, briefing, tag cloud, suggested connections."""
from __future__ import annotations

import math
import random
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import plotly.graph_objects as go
import streamlit as st

from ui.app_state import (
    get_link_suggester,
    get_vault_manager,
    get_vault_stats,
    init_session_state,
)
from ui.components.note_card import note_card_html

init_session_state()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _render_tag_cloud(tags_with_counts: list[tuple[str, int]]) -> None:
    items = tags_with_counts[:30]
    if not items:
        st.info("Keine Tags vorhanden.")
        return
    texts = [t for t, _ in items]
    counts = [c for _, c in items]
    max_c = max(counts, default=1)
    font_sizes = [13 + int(22 * c / max_c) for c in counts]
    _COLORS = ["#89b4fa", "#a6e3a1", "#cba6f7", "#fab387", "#f38ba8", "#94e2d5"]
    colors = [_COLORS[i % len(_COLORS)] for i in range(len(texts))]

    random.seed(42)
    n = len(texts)
    x_coords, y_coords = [], []
    for i in range(n):
        angle = (2 * math.pi * i / n) + random.uniform(-0.4, 0.4)
        r = 0.25 + random.uniform(0, 0.35)
        x_coords.append(0.5 + r * math.cos(angle))
        y_coords.append(0.5 + r * math.sin(angle))

    fig = go.Figure(
        go.Scatter(
            x=x_coords, y=y_coords,
            mode="text", text=texts,
            textfont={"size": font_sizes, "color": colors},
            hovertemplate="%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis={"visible": False, "range": [0, 1]},
        yaxis={"visible": False, "range": [0, 1]},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_top_tags_bar(tags: list[tuple[str, int]]) -> None:
    top5 = tags[:5]
    if not top5:
        return
    st.markdown("**Häufigste Tags:**")
    for tag, cnt in top5:
        bar_pct = int(100 * cnt / top5[0][1])
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="color:#89b4fa;min-width:90px;font-size:12px;">{tag}</span>'
            f'<div style="background:#45475a;border-radius:4px;height:10px;width:100%;max-width:140px;">'
            f'<div style="background:#89b4fa;border-radius:4px;height:10px;width:{bar_pct}%;"></div>'
            f'</div><span style="color:#6c7086;font-size:11px;">{cnt}</span></div>',
            unsafe_allow_html=True,
        )


def _render_recent_notes(recent: list[dict]) -> None:
    if not recent:
        st.info("Noch keine Notizen vorhanden. Erstelle deine erste Notiz!")
        return
    for note in recent:
        card_col, btn_col = st.columns([5, 1])
        with card_col:
            st.markdown(note_card_html(note), unsafe_allow_html=True)
        with btn_col:
            st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
            if st.button("📖", key=f"dash_open_{note['filename']}", help="Notiz öffnen"):
                st.session_state["current_note"] = note["filename"]
                st.switch_page("pages/02_Notes.py")


def _render_briefing() -> None:
    from core.config import BASE_DIR
    today_file = BASE_DIR / "data" / "briefings" / f"{datetime.now().strftime('%Y-%m-%d')}.md"

    if today_file.exists():
        with st.expander("Briefing anzeigen", expanded=True):
            raw = today_file.read_text(encoding="utf-8").splitlines()
            # Strip YAML frontmatter
            start = 0
            if raw and raw[0].strip() == "---":
                for i, line in enumerate(raw[1:], 1):
                    if line.strip() == "---":
                        start = i + 1
                        break
            st.markdown("\n".join(raw[start:]))
    else:
        st.info("Noch kein Briefing für heute.")
        if st.button("📋 Tages-Briefing generieren", type="primary"):
            with st.spinner("Analysiere Vault und generiere Briefing…"):
                try:
                    from ai.briefing_agent import BriefingAgent
                    BriefingAgent().generate_daily_briefing()
                    st.success("Briefing erstellt!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fehler beim Erstellen: {exc}")


def _render_suggested_connections() -> None:
    try:
        suggester = get_link_suggester()
        vm = get_vault_manager()
        if not suggester or not vm.get_all_notes():
            st.caption("Keine Verbindungsvorschläge (Vault leer).")
            return
        orphan_sugg = suggester.get_orphan_suggestions()[:3]
    except Exception:
        st.caption("Verbindungsvorschläge nicht verfügbar (benötigt Ollama).")
        return

    if not orphan_sugg:
        st.caption("Alle Notizen sind bereits vernetzt – gut gemacht!")
        return

    for item in orphan_sugg:
        orphan = item.get("orphan", {})
        suggestions = item.get("suggestions", [])[:2]
        if suggestions:
            targets = " / ".join(f"`{s['title']}`" for s in suggestions)
            st.markdown(
                f"**{orphan.get('title', '?')}** könnte verlinkt werden mit {targets}"
            )


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

st.markdown(
    f"<h1>📊 Dashboard</h1>"
    f"<p style='color:#6c7086;'>{datetime.now().strftime('%A, %d. %B %Y')}</p>",
    unsafe_allow_html=True,
)
st.divider()

# Metric row
try:
    stats = get_vault_stats()
except Exception:
    stats = {"total_notes": 0, "total_words": 0, "total_tags": 0, "total_links": 0}

c1, c2, c3, c4 = st.columns(4)
c1.metric("📝 Notizen", stats.get("total_notes", 0))
c2.metric("📊 Wörter", f"{stats.get('total_words', 0):,}")
c3.metric("🏷️ Tags", stats.get("total_tags", 0))
c4.metric("🔗 Links", stats.get("total_links", 0))

st.divider()

col_main, col_right = st.columns([3, 2])

with col_main:
    st.markdown("### 🕐 Zuletzt bearbeitet")
    try:
        from core.database import get_recent_notes
        recent = get_recent_notes(n=5)
    except Exception:
        recent = []
    _render_recent_notes(recent)

    st.divider()
    st.markdown("### 📋 Tages-Briefing")
    _render_briefing()

    st.divider()
    st.markdown("### 🔗 Vorgeschlagene Verbindungen")
    _render_suggested_connections()

with col_right:
    st.markdown("### 🏷️ Tag-Cloud")
    try:
        from core.database import get_all_tags
        tags = get_all_tags()
    except Exception:
        tags = []
    _render_tag_cloud(tags)

    st.divider()
    st.markdown("### 📈 Tag-Häufigkeit")
    _render_top_tags_bar(tags)
