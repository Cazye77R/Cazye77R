"""Tests for ai/ module: OllamaClient, NoteEmbedder, RAGEngine.

All tests mock Ollama HTTP calls and use an in-memory ChromaDB so they
run without a running Ollama instance.
"""
from __future__ import annotations

import json
import sys
import io
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import uuid

import pytest
import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai.ollama_client import OllamaClient, OllamaConnectionError
from ai.embedder import NoteEmbedder
from ai.rag_engine import RAGEngine


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]


def _make_note(
    filename: str = "Test.md",
    title: str = "Test",
    content: str = "Testinhalt der Notiz.",
    tags: list[str] | None = None,
    wikilinks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "title": title,
        "content": content,
        "word_count": len(content.split()),
        "tags": tags or ["test"],
        "wikilinks": wikilinks or [],
        "created_at": datetime(2026, 4, 22),
        "modified_at": datetime(2026, 4, 22),
        "raw_text": content,
        "frontmatter": {},
        "filepath": f"/vault/{filename}",
    }


@pytest.fixture()
def mock_ollama() -> MagicMock:
    client = MagicMock(spec=OllamaClient)
    client.get_embedding.return_value = _FAKE_EMBEDDING
    client.chat.return_value = "Antwort des Assistenten."
    client.is_available.return_value = True
    client.list_models.return_value = ["llama3", "nomic-embed-text"]
    return client


@pytest.fixture()
def ephemeral_embedder(mock_ollama: MagicMock) -> NoteEmbedder:
    """NoteEmbedder backed by an in-memory ChromaDB collection.

    EphemeralClient shares a global store in chromadb 1.5+, so each test
    gets a uniquely named collection to guarantee isolation.
    """
    chroma = chromadb.EphemeralClient()
    col_name = f"test_{uuid.uuid4().hex}"
    embedder = NoteEmbedder.__new__(NoteEmbedder)
    embedder._chroma = chroma
    embedder._collection_name = col_name
    embedder._col = chroma.get_or_create_collection(
        col_name, metadata={"hnsw:space": "cosine"}
    )
    embedder._ollama = mock_ollama
    return embedder


@pytest.fixture()
def mock_vault_manager() -> MagicMock:
    vm = MagicMock()
    vm.get_all_notes.return_value = [
        _make_note("A.md", "Alpha", "Inhalt Alpha"),
        _make_note("B.md", "Beta", "Inhalt Beta"),
    ]
    vm.search_notes_fulltext.return_value = []
    vm.get_note.side_effect = lambda fn: _make_note(fn, fn.replace(".md", ""), f"Inhalt von {fn}")
    return vm


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class TestOllamaClientIsAvailable:
    def _make_response(self, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_returns_true_when_reachable(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=self._make_response(200)):
            assert client.is_available() is True

    def test_returns_false_on_connection_error(self):
        client = OllamaClient()
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.is_available() is False


class TestOllamaClientListModels:
    def _make_response(self, models: list[str]) -> MagicMock:
        body = json.dumps({"models": [{"name": m} for m in models]}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_returns_model_names(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=self._make_response(["llama3", "mistral"])):
            models = client.list_models()
        assert "llama3" in models
        assert "mistral" in models

    def test_returns_empty_on_error(self):
        import urllib.error
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.list_models() == []


class TestOllamaClientGetEmbedding:
    def _request_mock(self, embedding: list[float]) -> MagicMock:
        resp = MagicMock()
        resp.read.return_value = json.dumps({"embedding": embedding}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_returns_float_list(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=self._request_mock(_FAKE_EMBEDDING)):
            emb = client.get_embedding("test text")
        assert emb == _FAKE_EMBEDDING

    def test_raises_on_connection_error(self):
        import urllib.error
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(OllamaConnectionError):
                client.get_embedding("test")

    def test_raises_when_embedding_empty(self):
        client = OllamaClient()
        resp = MagicMock()
        resp.read.return_value = json.dumps({"embedding": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(OllamaConnectionError, match="Embedding"):
                client.get_embedding("test")


class TestOllamaClientChat:
    def _request_mock(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.read.return_value = json.dumps(
            {"message": {"role": "assistant", "content": content}}
        ).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_returns_content_string(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=self._request_mock("Hallo!")):
            result = client.chat([{"role": "user", "content": "Hallo"}])
        assert result == "Hallo!"

    def test_prepends_system_prompt(self):
        client = OllamaClient()
        captured: list[dict] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data)
            captured.append(body)
            resp = MagicMock()
            resp.read.return_value = json.dumps({"message": {"content": "ok"}}).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client.chat([{"role": "user", "content": "hi"}], system_prompt="Du bist ein Assistent.")
        msgs = captured[0]["messages"]
        assert msgs[0]["role"] == "system"
        assert "Assistent" in msgs[0]["content"]


class TestOllamaClientChatStream:
    def _stream_response(self, chunks: list[str]) -> MagicMock:
        lines = [
            json.dumps({"message": {"content": c}, "done": False}).encode() + b"\n"
            for c in chunks
        ]
        lines.append(json.dumps({"message": {"content": ""}, "done": True}).encode() + b"\n")
        resp = MagicMock()
        resp.readline.side_effect = lines + [b""]
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_yields_content_chunks(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=self._stream_response(["Hallo", " Welt"])):
            result = list(client.chat_stream([{"role": "user", "content": "hi"}]))
        assert result == ["Hallo", " Welt"]

    def test_raises_on_connection_error(self):
        import urllib.error
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(OllamaConnectionError):
                list(client.chat_stream([{"role": "user", "content": "hi"}]))


# ---------------------------------------------------------------------------
# NoteEmbedder
# ---------------------------------------------------------------------------

class TestNoteEmbedderEmbedNote:
    def test_stores_entry_in_collection(self, ephemeral_embedder):
        note = _make_note()
        ephemeral_embedder.embed_note(note)
        assert ephemeral_embedder.collection_count() == 1

    def test_uses_filename_as_id_for_short_note(self, ephemeral_embedder):
        note = _make_note("Short.md")
        ephemeral_embedder.embed_note(note)
        result = ephemeral_embedder._col.get(ids=["Short.md"])
        assert len(result["ids"]) == 1

    def test_replaces_existing_embedding(self, ephemeral_embedder):
        note = _make_note("Replace.md")
        ephemeral_embedder.embed_note(note)
        ephemeral_embedder.embed_note(note)
        assert ephemeral_embedder.collection_count() == 1

    def test_metadata_contains_filename(self, ephemeral_embedder):
        note = _make_note("Meta.md", title="Meta Test")
        ephemeral_embedder.embed_note(note)
        result = ephemeral_embedder._col.get(ids=["Meta.md"], include=["metadatas"])
        assert result["metadatas"][0]["filename"] == "Meta.md"

    def test_metadata_contains_title(self, ephemeral_embedder):
        note = _make_note("T.md", title="Mein Titel")
        ephemeral_embedder.embed_note(note)
        result = ephemeral_embedder._col.get(ids=["T.md"], include=["metadatas"])
        assert result["metadatas"][0]["title"] == "Mein Titel"

    def test_large_note_creates_multiple_chunks(self, ephemeral_embedder):
        long_content = " ".join(["wort"] * 2500)
        note = _make_note("Big.md", content=long_content)
        note["word_count"] = 2500
        ephemeral_embedder.embed_note(note)
        assert ephemeral_embedder.collection_count() > 1

    def test_chunk_ids_use_index_suffix(self, ephemeral_embedder):
        long_content = " ".join(["wort"] * 2500)
        note = _make_note("Chunked.md", content=long_content)
        note["word_count"] = 2500
        ephemeral_embedder.embed_note(note)
        result = ephemeral_embedder._col.get(include=["metadatas"])
        filenames = {m["filename"] for m in result["metadatas"]}
        assert "Chunked.md" in filenames

    def test_calls_ollama_get_embedding(self, ephemeral_embedder, mock_ollama):
        note = _make_note()
        ephemeral_embedder.embed_note(note)
        mock_ollama.get_embedding.assert_called()


class TestNoteEmbedderDeleteEmbedding:
    def test_removes_entry(self, ephemeral_embedder):
        note = _make_note("ToDelete.md")
        ephemeral_embedder.embed_note(note)
        ephemeral_embedder.delete_embedding("ToDelete.md")
        assert ephemeral_embedder.collection_count() == 0

    def test_delete_nonexistent_does_not_raise(self, ephemeral_embedder):
        ephemeral_embedder.delete_embedding("ghost.md")


class TestNoteEmbedderEmbedAllNotes:
    def test_embeds_all_notes(self, ephemeral_embedder):
        notes = [_make_note("a.md"), _make_note("b.md"), _make_note("c.md")]
        ephemeral_embedder.embed_all_notes(notes)
        assert ephemeral_embedder.collection_count() == 3

    def test_continues_on_single_failure(self, ephemeral_embedder, mock_ollama):
        mock_ollama.get_embedding.side_effect = [
            Exception("Embedding-Fehler"),
            _FAKE_EMBEDDING,
        ]
        notes = [_make_note("fail.md"), _make_note("ok.md")]
        ephemeral_embedder.embed_all_notes(notes)
        assert ephemeral_embedder.collection_count() == 1

    def test_empty_list_does_nothing(self, ephemeral_embedder):
        ephemeral_embedder.embed_all_notes([])
        assert ephemeral_embedder.collection_count() == 0


class TestNoteEmbedderReindexAll:
    def test_clears_and_rebuilds(self, ephemeral_embedder):
        ephemeral_embedder.embed_note(_make_note("old.md"))
        assert ephemeral_embedder.collection_count() == 1
        notes = [_make_note("new.md")]
        ephemeral_embedder.reindex_all(notes)
        assert ephemeral_embedder.collection_count() == 1
        result = ephemeral_embedder._col.get()
        assert "old.md" not in result["ids"]


class TestNoteEmbedderChunkStrategy:
    def test_short_note_single_chunk(self, ephemeral_embedder):
        note = _make_note(content=" ".join(["wort"] * 100))
        note["word_count"] = 100
        ephemeral_embedder.embed_note(note)
        assert ephemeral_embedder.collection_count() == 1

    def test_split_content_below_threshold(self, ephemeral_embedder):
        chunks = ephemeral_embedder._split_content(" ".join(["x"] * 1999))
        assert len(chunks) == 1

    def test_split_content_above_threshold(self, ephemeral_embedder):
        chunks = ephemeral_embedder._split_content(" ".join(["x"] * 2001))
        assert len(chunks) > 1

    def test_chunk_word_count(self, ephemeral_embedder):
        content = " ".join(["x"] * 3000)
        chunks = ephemeral_embedder._split_content(content)
        for chunk in chunks:
            assert len(chunk.split()) <= 500


# ---------------------------------------------------------------------------
# RAGEngine
# ---------------------------------------------------------------------------

@pytest.fixture()
def rag(ephemeral_embedder, mock_ollama, mock_vault_manager) -> RAGEngine:
    engine = RAGEngine.__new__(RAGEngine)
    engine._embedder = ephemeral_embedder
    engine._ollama = mock_ollama
    engine._vault = mock_vault_manager
    return engine


@pytest.fixture()
def rag_with_data(rag, ephemeral_embedder) -> RAGEngine:
    """RAGEngine pre-loaded with two embedded notes."""
    notes = [
        _make_note("A.md", "Alpha", "Inhalt Alpha"),
        _make_note("B.md", "Beta", "Inhalt Beta"),
    ]
    for note in notes:
        ephemeral_embedder.embed_note(note)
    return rag


class TestRAGEngineSearchSemantic:
    def test_returns_list(self, rag_with_data):
        results = rag_with_data.search_semantic("Alpha", n_results=2)
        assert isinstance(results, list)

    def test_result_has_required_keys(self, rag_with_data):
        results = rag_with_data.search_semantic("Alpha", n_results=1)
        assert len(results) >= 1
        for key in ("filename", "title", "excerpt", "score"):
            assert key in results[0]

    def test_score_between_0_and_1(self, rag_with_data):
        results = rag_with_data.search_semantic("Alpha")
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_returns_empty_when_collection_empty(self, rag):
        results = rag.search_semantic("anything")
        assert results == []

    def test_deduplicates_chunks(self, rag, ephemeral_embedder, mock_ollama):
        long_content = " ".join(["wort"] * 2500)
        note = _make_note("Big.md", content=long_content)
        note["word_count"] = 2500
        ephemeral_embedder.embed_note(note)
        results = rag.search_semantic("wort", n_results=10)
        filenames = [r["filename"] for r in results]
        assert filenames.count("Big.md") == 1


class TestRAGEngineSearchHybrid:
    def test_combines_semantic_and_fulltext(self, rag_with_data, mock_vault_manager):
        mock_vault_manager.search_notes_fulltext.return_value = [
            _make_note("Extra.md", "Extra", "Volltext-Treffer"),
        ]
        results = rag_with_data.search_hybrid("Treffer", n_results=8)
        filenames = [r["filename"] for r in results]
        assert "Extra.md" in filenames

    def test_no_duplicate_filenames(self, rag_with_data, mock_vault_manager):
        # fulltext returns same notes as semantic
        mock_vault_manager.search_notes_fulltext.return_value = [
            _make_note("A.md", "Alpha", "Inhalt"),
        ]
        results = rag_with_data.search_hybrid("Alpha")
        filenames = [r["filename"] for r in results]
        assert len(filenames) == len(set(filenames))

    def test_sorted_by_score_descending(self, rag_with_data):
        results = rag_with_data.search_hybrid("Alpha")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestRAGEngineAnswerQuestion:
    def test_returns_answer_and_sources(self, rag_with_data):
        result = rag_with_data.answer_question("Was ist Alpha?")
        assert "answer" in result
        assert "sources" in result

    def test_answer_is_string(self, rag_with_data):
        result = rag_with_data.answer_question("Frage?")
        assert isinstance(result["answer"], str)

    def test_sources_are_list(self, rag_with_data):
        result = rag_with_data.answer_question("Frage?")
        assert isinstance(result["sources"], list)

    def test_calls_chat_with_system_prompt(self, rag_with_data, mock_ollama):
        rag_with_data.answer_question("Frage?")
        call_args = mock_ollama.chat.call_args
        assert call_args.kwargs.get("system_prompt") or call_args.args[1]

    def test_accepts_explicit_context_notes(self, rag_with_data, mock_ollama):
        context = [{"filename": "A.md", "title": "Alpha", "excerpt": "...", "score": 0.9}]
        rag_with_data.answer_question("Frage?", context_notes=context)
        mock_ollama.chat.assert_called_once()


class TestRAGEngineSummarizeNote:
    def test_returns_string(self, rag):
        summary = rag.summarize_note(_make_note())
        assert isinstance(summary, str)

    def test_calls_ollama_chat(self, rag, mock_ollama):
        rag.summarize_note(_make_note())
        mock_ollama.chat.assert_called_once()

    def test_truncates_long_content(self, rag, mock_ollama):
        long_note = _make_note(content=" ".join(["wort"] * 10000))
        rag.summarize_note(long_note)
        call_content = mock_ollama.chat.call_args.args[0][0]["content"]
        assert len(call_content) < 15000  # must be significantly shorter than full


class TestRAGEngineFindRelatedNotes:
    def test_excludes_self(self, rag_with_data):
        note = _make_note("A.md", "Alpha", "Inhalt Alpha")
        related = rag_with_data.find_related_notes(note, n=5)
        filenames = [r["filename"] for r in related]
        assert "A.md" not in filenames

    def test_returns_at_most_n(self, rag_with_data):
        note = _make_note("A.md")
        related = rag_with_data.find_related_notes(note, n=1)
        assert len(related) <= 1

    def test_returns_empty_on_empty_collection(self, rag):
        related = rag.find_related_notes(_make_note())
        assert related == []

    def test_result_has_score(self, rag_with_data):
        note = _make_note("A.md")
        related = rag_with_data.find_related_notes(note, n=5)
        for r in related:
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0
