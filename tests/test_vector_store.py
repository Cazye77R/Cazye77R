"""Tests for the ChromaDB-based RAG layer.

Ollama HTTP calls are mocked throughout; ChromaDB runs in-memory via
EphemeralClient so no filesystem side-effects occur.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from elephant.memory.markdown_store import save_memory, update_memory
from elephant.memory.vector_store import (
    _chunk_text,
    _source_key,
    delete_embedded,
    embed_memory,
    init_collection,
    search_similar,
    sync_all_memories,
)

FAKE_DIM = 768
FAKE_EMBEDDING = [0.1] * FAKE_DIM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_ollama():
    """Patch every requests.post in vector_store to return a fake embedding."""
    resp = MagicMock()
    resp.json.return_value = {"embedding": FAKE_EMBEDDING}
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.vector_store.requests.post", return_value=resp) as m:
        yield m


@pytest.fixture()
def tmp_memories(tmp_path, monkeypatch):
    """Redirect settings.memories_base_path to a temp directory."""
    for cat in ("general", "projects", "conversations"):
        (tmp_path / cat).mkdir()

    import elephant.config as cfg
    import elephant.memory.markdown_store as store
    import elephant.memory.vector_store as vs

    monkeypatch.setattr(cfg.settings, "memory_path", tmp_path)
    monkeypatch.setattr(store.settings, "memory_path", tmp_path)
    monkeypatch.setattr(vs.settings, "memory_path", tmp_path)
    return tmp_path


@pytest.fixture()
def coll(tmp_path):
    """Fresh, fully isolated ChromaDB collection per test.

    Uses PersistentClient with a per-test tmp_path because EphemeralClient
    shares a single in-process store across all instances in chromadb >= 1.0.
    """
    client = chromadb.PersistentClient(path=str(tmp_path / "chromadb"))
    return init_collection(client)


@pytest.fixture()
def coll_with_memory(coll, tmp_memories):
    """Collection pre-loaded with one memory."""
    path = save_memory("general", "Python Tips", "Use list comprehensions.\n\nAvoid global state.", ["python"], 0.8)
    embed_memory(path, collection=coll)
    return coll, path


# ---------------------------------------------------------------------------
# init_collection
# ---------------------------------------------------------------------------

def test_init_collection_returns_collection(coll):
    assert coll is not None
    assert coll.name == "memories"


def test_init_collection_idempotent():
    client = chromadb.EphemeralClient()
    c1 = init_collection(client)
    c2 = init_collection(client)
    assert c1.name == c2.name


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------

def test_chunk_text_single_short_paragraph():
    chunks = _chunk_text("Title", "Short content.")
    assert len(chunks) == 1
    assert chunks[0].startswith("# Title\n\n")
    assert "Short content." in chunks[0]


def test_chunk_text_title_prefix_in_every_chunk():
    # Build content that will span multiple chunks (>500 tokens ≈ 2000 chars)
    para = "word " * 200  # ~800 chars per paragraph
    content = f"{para}\n\n{para}\n\n{para}"
    chunks = _chunk_text("My Title", content)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.startswith("# My Title\n\n")


def test_chunk_text_overlap_carries_trailing_para():
    # P1 short (fits in overlap budget); P2 large (overflows limit alone).
    # Expected: chunk0=[P1], chunk1=[P1-as-overlap, P2], chunk2=[P3]
    # P1 ≤ overlap_chars (200) so it should appear at the start of chunk1.
    short_para = "x " * 25       # 50 chars — well within 200-char overlap budget
    big_para = "y " * 1000       # 2000 chars — overflows the 2000-char chunk limit
    content = f"{short_para}\n\n{big_para}\n\n{short_para}"
    chunks = _chunk_text("T", content)
    # Must have produced multiple chunks
    assert len(chunks) >= 2
    # The overlap mechanism should carry short_para into chunk1
    assert short_para.strip() in chunks[1]


def test_chunk_text_empty_content():
    chunks = _chunk_text("Empty", "")
    assert chunks == []


def test_chunk_text_whitespace_only():
    chunks = _chunk_text("Ws", "   \n\n   ")
    assert chunks == []


# ---------------------------------------------------------------------------
# embed_memory
# ---------------------------------------------------------------------------

def test_embed_memory_adds_documents(coll, tmp_memories):
    path = save_memory("general", "Hello", "Some content here.", [], 0.5)
    n = embed_memory(path, collection=coll)
    assert n >= 1
    assert coll.count() == n


def test_embed_memory_stores_metadata(coll, tmp_memories):
    path = save_memory("projects", "My Project", "Details here.", ["ai", "python"], 0.9)
    embed_memory(path, collection=coll)

    results = coll.get(where={"source_file": _source_key(path)})
    assert results["ids"]
    meta = results["metadatas"][0]
    assert meta["title"] == "My Project"
    assert meta["category"] == "projects"
    assert meta["importance"] == 0.9
    assert json.loads(meta["tags"]) == ["ai", "python"]
    assert "updated_at" in meta


def test_embed_memory_long_content_creates_multiple_chunks(coll, tmp_memories):
    long_para = "word " * 200  # ~800 chars
    content = f"{long_para}\n\n{long_para}\n\n{long_para}"
    path = save_memory("general", "Long", content, [])
    n = embed_memory(path, collection=coll)
    assert n >= 2


def test_embed_memory_deduplicates_on_reembed(coll, tmp_memories):
    path = save_memory("general", "Dedupe", "Original content.", [])
    embed_memory(path, collection=coll)
    count_after_first = coll.count()

    # Re-embed without changing the file
    embed_memory(path, collection=coll)
    assert coll.count() == count_after_first


def test_embed_memory_replaces_on_content_change(coll, tmp_memories):
    path = save_memory("general", "Replaceable", "v1", [])
    embed_memory(path, collection=coll)

    update_memory(path, content="v2 with more content here")
    embed_memory(path, collection=coll)

    results = coll.get(where={"source_file": _source_key(path)})
    assert all("v2" in doc for doc in results["documents"])


def test_embed_memory_chunk_index_metadata(coll, tmp_memories):
    long_para = "word " * 200
    content = f"{long_para}\n\n{long_para}\n\n{long_para}"
    path = save_memory("general", "Indexed", content, [])
    n = embed_memory(path, collection=coll)
    results = coll.get(where={"source_file": _source_key(path)})
    indices = {m["chunk_index"] for m in results["metadatas"]}
    assert indices == set(range(n))


# ---------------------------------------------------------------------------
# sync_all_memories
# ---------------------------------------------------------------------------

def test_sync_all_memories_embeds_new_files(coll, tmp_memories):
    save_memory("general", "A", "content a", [])
    save_memory("projects", "B", "content b", [])
    report = sync_all_memories(collection=coll)
    assert report["synced"] == 2
    assert report["skipped"] == 0
    assert report["total"] == 2


def test_sync_all_memories_skips_unchanged(coll, tmp_memories):
    save_memory("general", "Stable", "unchanged", [])
    sync_all_memories(collection=coll)   # first run
    report = sync_all_memories(collection=coll)  # second run
    assert report["synced"] == 0
    assert report["skipped"] == 1


def test_sync_all_memories_reembeds_changed(coll, tmp_memories):
    path = save_memory("general", "Changing", "v1", [])
    sync_all_memories(collection=coll)

    # Wait a tiny moment so updated_at differs from created_at
    time.sleep(0.01)
    update_memory(path, content="v2 new content here")
    report = sync_all_memories(collection=coll)
    assert report["synced"] == 1
    assert report["skipped"] == 0


def test_sync_all_memories_empty_dir(coll, tmp_memories):
    report = sync_all_memories(collection=coll)
    assert report == {"synced": 0, "skipped": 0, "total": 0}


def test_sync_all_memories_mixed(coll, tmp_memories):
    path_a = save_memory("general", "Stable A", "v1", [])
    path_b = save_memory("general", "Changing B", "v1", [])
    sync_all_memories(collection=coll)

    time.sleep(0.01)
    update_memory(path_b, content="v2")
    report = sync_all_memories(collection=coll)
    assert report["synced"] == 1
    assert report["skipped"] == 1


# ---------------------------------------------------------------------------
# search_similar
# ---------------------------------------------------------------------------

def test_search_similar_empty_collection(coll):
    results = search_similar("anything", collection=coll)
    assert results == []


def test_search_similar_returns_results(coll_with_memory):
    coll, _ = coll_with_memory
    results = search_similar("list comprehensions", collection=coll)
    assert len(results) >= 1


def test_search_similar_result_keys(coll_with_memory):
    coll, _ = coll_with_memory
    result = search_similar("python", collection=coll)[0]
    assert "chunk" in result
    assert "metadata" in result
    assert "score" in result
    assert "source_file" in result


def test_search_similar_score_range(coll_with_memory):
    coll, _ = coll_with_memory
    results = search_similar("python", collection=coll)
    for r in results:
        assert -1.0 <= r["score"] <= 1.0


def test_search_similar_tags_deserialized(coll_with_memory):
    coll, _ = coll_with_memory
    result = search_similar("python", collection=coll)[0]
    assert isinstance(result["metadata"]["tags"], list)


def test_search_similar_respects_top_k(coll, tmp_memories):
    for i in range(5):
        path = save_memory("general", f"Doc {i}", f"content {i}", [])
        embed_memory(path, collection=coll)
    results = search_similar("content", top_k=2, collection=coll)
    assert len(results) <= 2


def test_search_similar_category_filter(coll, tmp_memories):
    p1 = save_memory("general", "General Doc", "general content", [])
    p2 = save_memory("projects", "Project Doc", "project content", [])
    embed_memory(p1, collection=coll)
    embed_memory(p2, collection=coll)

    results = search_similar("content", category_filter="projects", collection=coll)
    assert all(r["metadata"]["category"] == "projects" for r in results)


def test_search_similar_importance_filter(coll, tmp_memories):
    p_low = save_memory("general", "Low", "some content here", [], importance=0.2)
    p_high = save_memory("general", "High", "some content here", [], importance=0.9)
    embed_memory(p_low, collection=coll)
    embed_memory(p_high, collection=coll)

    results = search_similar("content", min_importance=0.5, collection=coll)
    assert all(r["metadata"]["importance"] >= 0.5 for r in results)
    assert any(r["metadata"]["title"] == "High" for r in results)


def test_search_similar_source_file_populated(coll_with_memory):
    coll, path = coll_with_memory
    results = search_similar("python", collection=coll)
    assert results[0]["source_file"] == _source_key(path)


# ---------------------------------------------------------------------------
# delete_embedded
# ---------------------------------------------------------------------------

def test_delete_embedded_removes_all_chunks(coll, tmp_memories):
    long_para = "word " * 200
    content = f"{long_para}\n\n{long_para}\n\n{long_para}"
    path = save_memory("general", "Deletable", content, [])
    n = embed_memory(path, collection=coll)
    assert n >= 2

    delete_embedded(path, collection=coll)
    remaining = coll.get(where={"source_file": _source_key(path)})
    assert remaining["ids"] == []


def test_delete_embedded_leaves_other_files(coll, tmp_memories):
    p1 = save_memory("general", "Keep Me", "keep content", [])
    p2 = save_memory("general", "Delete Me", "delete content", [])
    embed_memory(p1, collection=coll)
    embed_memory(p2, collection=coll)

    delete_embedded(p2, collection=coll)

    assert coll.count() >= 1
    kept = coll.get(where={"source_file": _source_key(p1)})
    assert kept["ids"]


def test_delete_embedded_noop_if_not_present(coll, tmp_memories):
    path = save_memory("general", "Ghost", "ghost content", [])
    # Never embedded — should not raise
    delete_embedded(path, collection=coll)
    assert coll.count() == 0


def test_delete_embedded_accepts_string_path(coll, tmp_memories):
    path = save_memory("general", "Str Path", "content", [])
    embed_memory(path, collection=coll)
    delete_embedded(str(path), collection=coll)
    assert coll.count() == 0
