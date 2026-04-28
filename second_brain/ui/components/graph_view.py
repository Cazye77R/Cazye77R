"""pyvis graph configuration helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

_TAG_COLORS = [
    "#89b4fa",  # blue
    "#a6e3a1",  # green
    "#cba6f7",  # mauve
    "#fab387",  # peach
    "#f38ba8",  # red
    "#94e2d5",  # teal
    "#f9e2af",  # yellow
    "#74c7ec",  # sky
]

_ORPHAN_COLOR = "#585b70"
_EDGE_COLOR = "#6c7086"
_HIGHLIGHT_COLOR = "#f5c2e7"


def build_tag_color_map(notes: list[dict[str, Any]]) -> dict[str, str]:
    """Return a mapping of tag → hex color (stable across calls)."""
    seen: list[str] = []
    for note in notes:
        for tag in note.get("tags", []):
            if tag not in seen:
                seen.append(tag)
    return {tag: _TAG_COLORS[i % len(_TAG_COLORS)] for i, tag in enumerate(seen)}


def node_color(
    tags: list[str],
    tag_color_map: dict[str, str],
    is_orphan: bool = False,
    highlight_tag: str | None = None,
) -> str:
    if is_orphan:
        return _ORPHAN_COLOR
    if highlight_tag and highlight_tag in tags:
        return _HIGHLIGHT_COLOR
    for tag in tags:
        if tag in tag_color_map:
            return tag_color_map[tag]
    return "#45475a"


def legend_html(tag_color_map: dict[str, str]) -> str:
    if not tag_color_map:
        return ""
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px;'
        f'margin-bottom:4px;font-size:12px;color:#cdd6f4;">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{color};'
        f'display:inline-block;flex-shrink:0;"></span>{tag}</span>'
        for tag, color in list(tag_color_map.items())[:12]
    )
    return (
        f'<div style="background:#2a2a3e;border:1px solid #45475a;border-radius:8px;'
        f'padding:10px 14px;margin-bottom:8px;flex-wrap:wrap;display:flex;">{items}</div>'
    )


def build_pyvis_html(
    notes: list[dict[str, Any]],
    graph,  # nx.DiGraph
    min_connections: int = 0,
    highlight_tag: str | None = None,
    show_orphans: bool = True,
    output_path: str | Path | None = None,
) -> str:
    """Build and return the pyvis HTML string. Optionally also write to output_path."""
    from pyvis.network import Network

    tag_color_map = build_tag_color_map(notes)
    degree = dict(graph.degree())
    orphans = {n for n in graph.nodes if graph.degree(n) == 0}

    net = Network(
        height="680px",
        width="100%",
        bgcolor="#1e1e2e",
        font_color="#cdd6f4",
        directed=True,
        notebook=False,
    )
    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=180,
        spring_strength=0.05,
        damping=0.09,
        overlap=0,
    )
    net.set_options("""
    {
      "interaction": {
        "hover": true,
        "tooltipDelay": 150,
        "navigationButtons": true
      },
      "edges": {
        "smooth": { "type": "dynamic" }
      }
    }
    """)

    # Build filename → note metadata lookup
    note_meta: dict[str, dict] = {}
    for n in notes:
        from pathlib import Path as _P
        stem = _P(n["filename"]).stem
        note_meta[stem] = n

    included: set[str] = set()

    for node, attrs in graph.nodes(data=True):
        deg = degree.get(node, 0)
        is_orphan = node in orphans

        if deg < min_connections and not is_orphan:
            continue
        if is_orphan and not show_orphans:
            continue

        included.add(node)

        tags = attrs.get("tags", [])
        color = node_color(tags, tag_color_map, is_orphan, highlight_tag)
        size = 14 + min(deg * 4, 40)
        label = attrs.get("title", node)
        if len(label) > 24:
            label = label[:22] + "…"

        title_html = (
            f"<b>{attrs.get('title', node)}</b><br>"
            f"Tags: {', '.join(tags) or '–'}<br>"
            f"Verbindungen: {deg}<br>"
            f"Wörter: {attrs.get('word_count', 0)}"
        )

        border_color = _HIGHLIGHT_COLOR if (highlight_tag and highlight_tag in tags) else color
        net.add_node(
            node,
            label=label,
            title=title_html,
            size=size,
            color={"background": color, "border": border_color, "highlight": {"background": _HIGHLIGHT_COLOR}},
            font={"size": 13},
        )

    for source, target in graph.edges():
        if source in included and target in included:
            net.add_edge(source, target, color=_EDGE_COLOR, arrows="to", width=1.2)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        net.save_graph(str(output_path))
        return output_path.read_text(encoding="utf-8")

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = f.name
    net.save_graph(tmp)
    html = Path(tmp).read_text(encoding="utf-8")
    os.unlink(tmp)
    return html
