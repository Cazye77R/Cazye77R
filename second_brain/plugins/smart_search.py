"""Multi-mode search plugin: semantic, fulltext, hybrid, tag."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ai.ollama_client import OllamaConnectionError


@dataclass
class SearchResult:
    filename: str
    title: str
    excerpt: str
    tags: list[str]
    score: float
    match_type: str  # "semantic" | "fulltext" | "hybrid" | "tag"


class SmartSearch:
    def __init__(
        self,
        rag: Any | None = None,
        vault_manager: Any | None = None,
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, mode: str = "hybrid") -> list[SearchResult]:
        dispatch = {
            "semantic": self._search_semantic,
            "fulltext": self._search_fulltext,
            "hybrid": self._search_hybrid,
            "tag": self._search_tag,
        }
        fn = dispatch.get(mode, self._search_hybrid)
        return fn(query)

    def highlight_matches(self, text: str, query: str) -> str:
        terms = [re.escape(t) for t in query.split() if len(t) >= 2]
        if not terms:
            return text
        pattern = re.compile(f"({'|'.join(terms)})", re.IGNORECASE)
        return pattern.sub(r"**\1**", text)

    # ------------------------------------------------------------------
    # Search implementations
    # ------------------------------------------------------------------

    def _search_semantic(self, query: str) -> list[SearchResult]:
        try:
            raw = self._rag.search_semantic(query, n_results=10)
        except OllamaConnectionError:
            return self._search_fulltext(query)

        results = []
        for r in raw:
            note = self._vault.get_note(r["filename"])
            tags = note["tags"] if note else []
            results.append(
                SearchResult(
                    filename=r["filename"],
                    title=r["title"],
                    excerpt=r["excerpt"],
                    tags=tags,
                    score=r["score"],
                    match_type="semantic",
                )
            )
        return results

    def _search_fulltext(self, query: str) -> list[SearchResult]:
        notes = self._vault.search_notes_fulltext(query)
        results = []
        for note in notes:
            excerpt = self._make_excerpt(note["content"], query)
            results.append(
                SearchResult(
                    filename=note["filename"],
                    title=note["title"],
                    excerpt=excerpt,
                    tags=note.get("tags", []),
                    score=1.0,  # binary match; no ranking
                    match_type="fulltext",
                )
            )
        return results

    def _search_hybrid(self, query: str) -> list[SearchResult]:
        try:
            raw = self._rag.search_hybrid(query, n_results=10)
        except OllamaConnectionError:
            return self._search_fulltext(query)

        results = []
        seen: set[str] = set()
        for r in raw:
            if r["filename"] in seen:
                continue
            seen.add(r["filename"])
            note = self._vault.get_note(r["filename"])
            tags = note["tags"] if note else []
            results.append(
                SearchResult(
                    filename=r["filename"],
                    title=r["title"],
                    excerpt=r["excerpt"],
                    tags=tags,
                    score=r["score"],
                    match_type="hybrid",
                )
            )
        return results

    def _search_tag(self, query: str) -> list[SearchResult]:
        tag = query.lstrip("#").strip().lower()
        notes = self._vault.get_all_notes()
        results = []
        for note in notes:
            note_tags = [t.lower() for t in note.get("tags", [])]
            if tag in note_tags or any(t.startswith(tag) for t in note_tags):
                results.append(
                    SearchResult(
                        filename=note["filename"],
                        title=note["title"],
                        excerpt=note["content"][:300],
                        tags=note["tags"],
                        score=1.0,
                        match_type="tag",
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_excerpt(self, content: str, query: str, length: int = 300) -> str:
        lower = content.lower()
        idx = lower.find(query.lower().split()[0]) if query.split() else -1
        if idx == -1:
            return content[:length]
        start = max(0, idx - 60)
        snippet = content[start : start + length]
        if start > 0:
            snippet = "..." + snippet
        return snippet
