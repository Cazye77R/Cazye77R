"""RAG pipeline: semantic search + hybrid search + LLM answering."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai.embedder import NoteEmbedder
from ai.ollama_client import OllamaClient
from core.config import VAULT_DIR

_SYSTEM_PROMPT = (
    "Du bist ein persönlicher Wissensassistent. "
    "Antworte NUR basierend auf den gegebenen Notizen. "
    "Wenn die Antwort nicht in den Notizen steht, sage das klar. "
    "Antworte auf Deutsch und sei präzise."
)

_SUMMARIZE_PROMPT = (
    "Du bist ein präziser Zusammenfasser. "
    "Antworte ausschließlich mit der Zusammenfassung, keine Einleitung."
)


class RAGEngine:
    def __init__(
        self,
        embedder: NoteEmbedder | None = None,
        ollama: OllamaClient | None = None,
        vault_manager: Any | None = None,
    ) -> None:
        self._embedder = embedder or NoteEmbedder()
        self._ollama = ollama or OllamaClient()
        if vault_manager is None:
            from core.vault_manager import VaultManager
            vault_manager = VaultManager(VAULT_DIR)
        self._vault = vault_manager

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_semantic(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        if self._embedder.collection_count() == 0:
            return []
        embedding = self._ollama.get_embedding(query)
        results = self._embedder._col.query(
            query_embeddings=[embedding],
            n_results=min(n_results, self._embedder.collection_count()),
            include=["documents", "metadatas", "distances"],
        )
        output = []
        seen_files: set[str] = set()
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            filename = meta.get("filename", "")
            if filename in seen_files:
                continue
            seen_files.add(filename)
            excerpt = doc[:300] + ("..." if len(doc) > 300 else "")
            output.append(
                {
                    "filename": filename,
                    "title": meta.get("title", ""),
                    "excerpt": excerpt,
                    "score": round(max(0.0, 1.0 - dist), 4),
                }
            )
        return output

    def search_hybrid(self, query: str, n_results: int = 8) -> list[dict[str, Any]]:
        semantic = self.search_semantic(query, n_results=n_results)
        seen_files = {r["filename"] for r in semantic}

        fulltext = self._vault.search_notes_fulltext(query)
        for note in fulltext[:n_results]:
            if note["filename"] not in seen_files:
                seen_files.add(note["filename"])
                excerpt = note["content"][:300] + ("..." if len(note["content"]) > 300 else "")
                semantic.append(
                    {
                        "filename": note["filename"],
                        "title": note["title"],
                        "excerpt": excerpt,
                        "score": 0.5,
                    }
                )

        return sorted(semantic, key=lambda x: x["score"], reverse=True)[:n_results]

    # ------------------------------------------------------------------
    # LLM operations
    # ------------------------------------------------------------------

    def answer_question(
        self,
        question: str,
        context_notes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if context_notes is None:
            context_notes = self.search_semantic(question, n_results=5)

        sources: list[dict[str, str]] = []
        context_parts: list[str] = []
        seen: set[str] = set()

        for result in context_notes[:5]:
            filename = result["filename"]
            if filename in seen:
                continue
            seen.add(filename)
            note = self._vault.get_note(filename)
            if note:
                context_parts.append(f"## {note['title']}\n{note['content']}")
                sources.append({"filename": filename, "title": note["title"]})

        context = (
            "\n\n---\n\n".join(context_parts)
            if context_parts
            else "Keine relevanten Notizen gefunden."
        )
        messages = [
            {
                "role": "user",
                "content": (
                    f"Kontext aus meinen Notizen:\n\n{context}\n\n"
                    f"Frage: {question}"
                ),
            }
        ]
        answer = self._ollama.chat(messages, system_prompt=_SYSTEM_PROMPT)
        return {"answer": answer, "sources": sources}

    def summarize_note(self, note_dict: dict[str, Any]) -> str:
        title = note_dict.get("title", "")
        content = note_dict.get("content", "")[:3000]
        messages = [
            {
                "role": "user",
                "content": (
                    f"Fasse die folgende Notiz in 2-3 prägnanten Sätzen zusammen.\n\n"
                    f"Titel: {title}\n\n{content}"
                ),
            }
        ]
        return self._ollama.chat(messages, system_prompt=_SUMMARIZE_PROMPT)

    def find_related_notes(
        self, note_dict: dict[str, Any], n: int = 5
    ) -> list[dict[str, Any]]:
        if self._embedder.collection_count() == 0:
            return []
        query_text = f"{note_dict.get('title', '')}\n{note_dict.get('content', '')}"
        embedding = self._ollama.get_embedding(query_text)
        current_filename = note_dict["filename"]

        raw = self._embedder._col.query(
            query_embeddings=[embedding],
            n_results=min(n + 5, self._embedder.collection_count()),
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict[str, Any]] = []
        seen = {current_filename}
        for doc, meta, dist in zip(
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
        ):
            filename = meta.get("filename", "")
            if filename in seen:
                continue
            seen.add(filename)
            output.append(
                {
                    "filename": filename,
                    "title": meta.get("title", ""),
                    "excerpt": doc[:200] + ("..." if len(doc) > 200 else ""),
                    "score": round(max(0.0, 1.0 - dist), 4),
                }
            )
            if len(output) >= n:
                break

        return output
