from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx


class NoteGraph:
    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_graph(self, notes_list: list[dict[str, Any]]) -> nx.DiGraph:
        self.graph = nx.DiGraph()

        # Add all notes as nodes first
        note_stems = {Path(n["filename"]).stem for n in notes_list}
        for note in notes_list:
            stem = Path(note["filename"]).stem
            self.graph.add_node(
                stem,
                title=note["title"],
                tags=note["tags"],
                word_count=note["word_count"],
            )

        # Add edges for each wikilink that resolves to a known note
        for note in notes_list:
            source = Path(note["filename"]).stem
            for link in note["wikilinks"]:
                target = Path(link).stem  # handle "Note.md" links too
                if target not in note_stems:
                    # Add dangling node so the link is visible in the graph
                    self.graph.add_node(target, title=target, tags=[], word_count=0)
                self.graph.add_edge(source, target)

        return self.graph

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_neighbors(self, note_name: str) -> dict[str, list[str]]:
        stem = Path(note_name).stem
        if stem not in self.graph:
            return {"outgoing": [], "incoming": []}
        return {
            "outgoing": list(self.graph.successors(stem)),
            "incoming": list(self.graph.predecessors(stem)),
        }

    def get_most_connected(self, n: int = 10) -> list[tuple[str, int]]:
        degree = dict(self.graph.degree())
        return sorted(degree.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_orphans(self) -> list[str]:
        return [
            node
            for node in self.graph.nodes
            if self.graph.degree(node) == 0
        ]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_pyvis(self, output_path: str | Path) -> Path:
        from pyvis.network import Network

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        net = Network(
            height="700px",
            width="100%",
            bgcolor="#1e1e2e",
            font_color="#cdd6f4",
            directed=True,
            notebook=False,
        )
        net.barnes_hut(spring_length=200, spring_strength=0.05, damping=0.09)

        degree = dict(self.graph.degree())

        for node, attrs in self.graph.nodes(data=True):
            size = 15 + degree.get(node, 0) * 5
            title_html = (
                f"<b>{attrs.get('title', node)}</b><br>"
                f"Tags: {', '.join(attrs.get('tags', [])) or '–'}<br>"
                f"Wörter: {attrs.get('word_count', 0)}"
            )
            net.add_node(
                node,
                label=attrs.get("title", node),
                title=title_html,
                size=size,
                color="#89b4fa",
            )

        for source, target in self.graph.edges():
            net.add_edge(source, target, color="#6c7086", arrows="to")

        net.save_graph(str(output_path))
        return output_path
