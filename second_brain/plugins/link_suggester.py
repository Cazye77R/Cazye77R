"""Link suggestion plugin with TTL caching."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

_TTL_SECONDS = 3600.0  # 1 hour


class _Cache:
    def __init__(self, ttl: float = _TTL_SECONDS) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[list[dict[str, Any]], float]] = {}

    def get(self, key: str) -> list[dict[str, Any]] | None:
        if key not in self._store:
            return None
        suggestions, ts = self._store[key]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return suggestions

    def set(self, key: str, suggestions: list[dict[str, Any]]) -> None:
        self._store[key] = (suggestions, time.monotonic())

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


class LinkSuggester:
    def __init__(
        self,
        rag: Any | None = None,
        vault_manager: Any | None = None,
        graph: Any | None = None,
        cache_ttl: float = _TTL_SECONDS,
    ) -> None:
        if rag is None:
            from ai.rag_engine import RAGEngine
            rag = RAGEngine()
        self._rag = rag
        if vault_manager is None:
            from core.vault_manager import VaultManager
            from core.config import VAULT_DIR
            vault_manager = VaultManager(VAULT_DIR)
        self._vault = vault_manager
        if graph is None:
            from core.graph_engine import NoteGraph
            graph = NoteGraph()
        self._graph = graph
        self._cache = _Cache(ttl=cache_ttl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_suggestions_for_note(self, filename: str) -> list[dict[str, Any]]:
        cached = self._cache.get(filename)
        if cached is not None:
            return cached

        note = self._vault.get_note(filename)
        if not note:
            return []

        suggestions = self._compute_suggestions(note)
        self._cache.set(filename, suggestions)
        return suggestions

    def get_orphan_suggestions(self) -> list[dict[str, Any]]:
        notes = self._vault.get_all_notes()
        if not notes:
            return []

        self._graph.build_graph(notes)
        orphans_names = self._graph.get_orphans()

        results: list[dict[str, Any]] = []
        for orphan_name in orphans_names:
            note = self._vault.get_note(f"{orphan_name}.md")
            if not note:
                note = self._vault.get_note(orphan_name)
            if not note:
                continue
            related = self._get_related(note, n=3)
            if related:
                results.append(
                    {
                        "orphan": {
                            "filename": note["filename"],
                            "title": note.get("title", orphan_name),
                        },
                        "suggestions": related,
                    }
                )

        return results

    def invalidate_cache(self, filename: str | None = None) -> None:
        if filename:
            self._cache.invalidate(filename)
        else:
            self._cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_suggestions(self, note: dict[str, Any]) -> list[dict[str, Any]]:
        existing_links = {Path(lnk).stem for lnk in note.get("wikilinks", [])}
        current_stem = Path(note["filename"]).stem

        related = self._get_related(note, n=8)

        return [
            {
                "filename": r["filename"],
                "title": r["title"],
                "excerpt": r.get("excerpt", ""),
                "score": r.get("score", 0.0),
                "already_linked": Path(r["filename"]).stem in existing_links,
            }
            for r in related
            if Path(r["filename"]).stem != current_stem
        ][:5]

    def _get_related(
        self, note: dict[str, Any], n: int = 5
    ) -> list[dict[str, Any]]:
        try:
            return self._rag.find_related_notes(note, n=n)
        except Exception:
            # Fallback: return other notes from vault
            all_notes = self._vault.get_all_notes()
            others = [
                {
                    "filename": n_["filename"],
                    "title": n_.get("title", n_["filename"]),
                    "excerpt": n_["content"][:200],
                    "score": 0.3,
                }
                for n_ in all_notes
                if n_["filename"] != note["filename"]
            ]
            return others[:n]
