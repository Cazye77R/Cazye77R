"""Knowledge graph visualization using pyvis."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import streamlit.components.v1 as components

from ui.app_state import get_all_tags_cached, get_vault_manager, init_session_state

init_session_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_graph(notes: list[dict]):
    from core.graph_engine import NoteGraph
    ng = NoteGraph()
    ng.build_graph(notes)
    return ng.graph


def _render_sidebar_node_info(stem: str, notes: list[dict]) -> None:
    from pathlib import Path as _P
    note_by_stem = {_P(n["filename"]).stem: n for n in notes}
    note = note_by_stem.get(stem)
    if not note:
        st.sidebar.markdown(f"**{stem}** (Dangling link – keine Notiz vorhanden)")
        return

    st.sidebar.markdown(f"### 📄 {note['title']}")
    tags = note.get("tags", [])
    if tags:
        from ui.components.note_card import tag_badge
        badges = "".join(tag_badge(t) for t in tags)
        st.sidebar.markdown(badges, unsafe_allow_html=True)
    st.sidebar.markdown(
        f"**Wörter:** {note.get('word_count', 0)}  \n"
        f"**Links:** {len(note.get('wikilinks', []))}"
    )
    if st.sidebar.button("📖 Notiz öffnen", use_container_width=True, key="graph_open_note"):
        st.session_state["current_note"] = note["filename"]
        st.switch_page("pages/02_Notes.py")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.markdown("<h1>🕸️ Wissensgraph</h1>", unsafe_allow_html=True)

vm = get_vault_manager()
try:
    notes = vm.get_all_notes()
except Exception:
    notes = []

if not notes:
    st.info("Noch keine Notizen im Vault. Erstelle zuerst einige Notizen.")
    st.stop()

# ── Controls ─────────────────────────────────────────────────────────────────
ctrl1, ctrl2, ctrl3 = st.columns([1, 2, 1])

with ctrl1:
    min_connections = st.slider(
        "Min. Verbindungen",
        min_value=0,
        max_value=10,
        value=0,
        key="graph_min_conn",
    )

with ctrl2:
    all_tags_flat: list[str] = []
    for n in notes:
        for t in n.get("tags", []):
            if t not in all_tags_flat:
                all_tags_flat.append(t)

    highlight_tag = st.selectbox(
        "Tag hervorheben",
        ["(keiner)"] + all_tags_flat,
        key="graph_highlight_tag",
    )
    hl = None if highlight_tag == "(keiner)" else highlight_tag

with ctrl3:
    show_orphans = st.toggle("Isolierte Knoten", value=True, key="graph_show_orphans")

st.divider()

# ── Build graph with session-state cache ──────────────────────────────────────
# Cache key encodes all settings that affect the graph rendering.
# The key includes note count + last-modified proxy so stale HTML is
# never shown after vault changes.
from ui.components.graph_view import build_pyvis_html, legend_html, build_tag_color_map

_cache_key = f"{len(notes)}|{min_connections}|{highlight_tag}|{show_orphans}"

if st.session_state.get("_graph_cache_key") != _cache_key:
    with st.spinner("Baue Graphen…"):
        graph = _build_graph(notes)
        tag_color_map = build_tag_color_map(notes)
        html = build_pyvis_html(
            notes=notes,
            graph=graph,
            min_connections=min_connections,
            highlight_tag=hl,
            show_orphans=show_orphans,
        )
        st.session_state["_graph_cache_key"] = _cache_key
        st.session_state["_graph_html"] = html
        st.session_state["_graph_obj"] = graph
        st.session_state["_graph_tag_color_map"] = tag_color_map
else:
    html = st.session_state["_graph_html"]
    graph = st.session_state["_graph_obj"]
    tag_color_map = st.session_state.get("_graph_tag_color_map", {})

# Tag color legend
if tag_color_map:
    st.markdown(legend_html(tag_color_map), unsafe_allow_html=True)

# Graph
components.html(html, height=700, scrolling=False)

# ── Stats sidebar ─────────────────────────────────────────────────────────────
st.sidebar.markdown("## 📊 Graph-Info")
n_nodes = graph.number_of_nodes()
n_edges = graph.number_of_edges()
orphan_count = sum(1 for nd in graph.nodes if graph.degree(nd) == 0)

st.sidebar.metric("Knoten", n_nodes)
st.sidebar.metric("Kanten", n_edges)
st.sidebar.metric("Isolierte Knoten", orphan_count)

st.sidebar.divider()

from core.graph_engine import NoteGraph as _NG
_ng_tmp = _NG()
_ng_tmp.graph = graph
top = _ng_tmp.get_most_connected(n=5)
if top:
    st.sidebar.markdown("**🔗 Bestvernetzte Notizen**")
    for stem, deg in top:
        st.sidebar.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:12px;color:#cdd6f4;margin-bottom:2px;">'
            f'<span>{stem}</span><span style="color:#89b4fa;">{deg}</span></div>',
            unsafe_allow_html=True,
        )

st.sidebar.divider()

st.sidebar.markdown("**🔎 Knoten suchen**")
node_stems = sorted(graph.nodes())
selected_node = st.sidebar.selectbox(
    "Knoten auswählen",
    ["—"] + node_stems,
    label_visibility="collapsed",
    key="graph_selected_node",
)
if selected_node and selected_node != "—":
    _render_sidebar_node_info(selected_node, notes)
