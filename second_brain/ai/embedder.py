"""ChromaDB-backed note embedder using Ollama for vector generation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from core.config import CHROMA_DIR

COLLECTION_NAME = "second_brain_notes"
_CHUNK_WORDS = 500      # words per chunk for large notes
_CHUNK_THRESHOLD = 2000  # notes with more words than this get chunked


class NoteEmbedder:
    def __init__(
        self,
        chroma_dir: str | Path = CHROMA_DIR,
        ollama_client: Any = None,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        chroma_dir = Path(chroma_dir)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._collection_name = collection_name
        self._chroma = chromadb.PersistentClient(path=str(chroma_dir))
        self._col = self._chroma.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        if ollama_client is None:
            from ai.ollama_client import OllamaClient
            ollama_client = OllamaClient()
        self._ollama = ollama_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_note(self, note_dict: dict[str, Any]) -> None:
        filename = note_dict["filename"]
        title = note_dict.get("title", filename)
        tags_str = ",".join(note_dict.get("tags", []))
        word_count = note_dict.get("word_count", 0)
        modified_at = str(note_dict.get("modified_at", ""))
        content = note_dict.get("content", "")

        self.delete_embedding(filename)

        chunks = self._split_content(content)
        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            chunk_id = filename if len(chunks) == 1 else f"{filename}_{i}"
            doc_text = f"{title}\nTags: {tags_str}\n\n{chunk[:2000]}"
            vector = self._ollama.get_embedding(doc_text)

            ids.append(chunk_id)
            embeddings.append(vector)
            documents.append(doc_text)
            metadatas.append(
                {
                    "filename": filename,
                    "title": title,
                    "tags_str": tags_str,
                    "word_count": word_count,
                    "modified_at": modified_at,
                    "chunk_index": i,
                    "chunk_total": len(chunks),
                }
            )

        self._col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def embed_all_notes(self, notes_list: list[dict[str, Any]]) -> None:
        total = len(notes_list)
        for i, note in enumerate(notes_list, 1):
            print(f"Embedding {i}/{total}: {note.get('title', note['filename'])}")
            try:
                self.embed_note(note)
            except Exception as exc:
                print(f"  ⚠ Embedding fehlgeschlagen ({note['filename']}): {exc}")

    def delete_embedding(self, filename: str) -> None:
        try:
            if self._col.count() > 0:
                self._col.delete(where={"filename": {"$eq": filename}})
        except Exception:
            pass

    def reindex_all(self, notes_list: list[dict[str, Any]]) -> None:
        self._chroma.delete_collection(self._collection_name)
        self._col = self._chroma.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embed_all_notes(notes_list)

    def collection_count(self) -> int:
        return self._col.count()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _split_content(self, content: str) -> list[str]:
        words = content.split()
        if len(words) <= _CHUNK_THRESHOLD:
            return [content]
        return [
            " ".join(words[i : i + _CHUNK_WORDS])
            for i in range(0, len(words), _CHUNK_WORDS)
        ]


# ---------------------------------------------------------------------------
# Module-level helpers (used by file_watcher and launcher)
# ---------------------------------------------------------------------------

_singleton: NoteEmbedder | None = None


def _get_embedder() -> NoteEmbedder:
    global _singleton
    if _singleton is None:
        _singleton = NoteEmbedder()
    return _singleton


def embed_note(note_dict: dict[str, Any]) -> None:
    _get_embedder().embed_note(note_dict)


def delete_embedding(filename: str) -> None:
    _get_embedder().delete_embedding(filename)


def ensure_indexed_from_vault(vault_path: str | Path) -> None:
    """Auto-index all vault notes if ChromaDB collection is empty."""
    embedder = _get_embedder()
    if embedder.collection_count() > 0:
        return
    from core.vault_manager import VaultManager
    notes = VaultManager(vault_path).get_all_notes()
    if not notes:
        return
    print(f"   🔍 ChromaDB leer – indexiere {len(notes)} Notizen...")
    embedder.embed_all_notes(notes)
