"""Tests for elephant.memory.consolidation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from elephant.memory.markdown_store import load_memory, save_memory
from elephant.memory.consolidation import consolidate_memories, find_consolidation_candidates
from elephant.memory.schemas import Memory, MemoryMetadata


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_memories(tmp_path, monkeypatch):
    """Redirect settings.memory_path to a temp directory."""
    for cat in ("general", "projects", "conversations"):
        (tmp_path / cat).mkdir()

    import elephant.config as cfg
    import elephant.memory.markdown_store as store
    import elephant.memory.vector_store as vs
    import elephant.memory.consolidation as cons_mod

    monkeypatch.setattr(cfg.settings, "memory_path", tmp_path)
    monkeypatch.setattr(store.settings, "memory_path", tmp_path)
    monkeypatch.setattr(vs.settings, "memory_path", tmp_path)
    monkeypatch.setattr(cons_mod.settings, "memory_path", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# find_consolidation_candidates — no similar memories → empty list
# ---------------------------------------------------------------------------

def test_find_candidates_empty_when_no_similar(tmp_memories):
    path = save_memory("general", "Unique Memory", "unique content about elephants", [])

    mock_coll = MagicMock()
    with patch("elephant.memory.consolidation.search_similar", return_value=[]):
        candidates = find_consolidation_candidates(mock_coll, threshold=0.8)

    assert candidates == []


# ---------------------------------------------------------------------------
# find_consolidation_candidates — returns pair when similarity >= threshold
# ---------------------------------------------------------------------------

def test_find_candidates_returns_pair_above_threshold(tmp_memories):
    path_a = save_memory("general", "Memory A", "content about Python", [])
    path_b = save_memory("general", "Memory B", "content about Python too", [])

    mock_result = [{"source_file": str(path_b.resolve()), "score": 0.9}]
    mock_coll = MagicMock()

    with patch("elephant.memory.consolidation.search_similar", return_value=mock_result):
        candidates = find_consolidation_candidates(mock_coll, threshold=0.8)

    assert len(candidates) == 1
    assert isinstance(candidates[0], tuple)
    assert len(candidates[0]) == 2


# ---------------------------------------------------------------------------
# find_consolidation_candidates — same pair not returned twice
# ---------------------------------------------------------------------------

def test_find_candidates_no_duplicate_pairs(tmp_memories):
    path_a = save_memory("general", "Mem A", "content A", [])
    path_b = save_memory("general", "Mem B", "content B", [])

    # Both memories match each other
    def _search_side_effect(query, top_k, collection):
        # Return the "other" file for whichever is queried first
        return [{"source_file": str(path_b.resolve()), "score": 0.95}]

    mock_coll = MagicMock()
    with patch("elephant.memory.consolidation.search_similar", side_effect=_search_side_effect):
        candidates = find_consolidation_candidates(mock_coll, threshold=0.8)

    # Even though both memories would match each other, the pair should appear only once
    assert len(candidates) <= 1


# ---------------------------------------------------------------------------
# consolidate_memories — calls Ollama and creates a merged file
# ---------------------------------------------------------------------------

def test_consolidate_creates_merged_file(tmp_memories):
    path_a = save_memory("general", "Fact A", "Python is great", [], importance=0.7)
    path_b = save_memory("general", "Fact B", "Python is versatile", [], importance=0.5)
    mem_a = load_memory(path_a)
    mem_b = load_memory(path_b)

    merged_text = "Python is great and versatile."
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": merged_text}}
    mock_resp.raise_for_status = MagicMock()

    with patch("elephant.memory.consolidation.requests.post", return_value=mock_resp):
        with patch("elephant.memory.consolidation.embed_memory"):
            with patch("elephant.memory.consolidation.delete_embedded"):
                result = consolidate_memories([mem_a, mem_b])

    assert result.content == merged_text
    assert result.filepath is not None
    assert result.filepath.exists()


# ---------------------------------------------------------------------------
# consolidate_memories — deletes original files
# ---------------------------------------------------------------------------

def test_consolidate_deletes_originals(tmp_memories):
    path_a = save_memory("general", "Delete A", "content A", [])
    path_b = save_memory("general", "Delete B", "content B", [])
    mem_a = load_memory(path_a)
    mem_b = load_memory(path_b)

    assert path_a.exists()
    assert path_b.exists()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "merged"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("elephant.memory.consolidation.requests.post", return_value=mock_resp):
        with patch("elephant.memory.consolidation.embed_memory"):
            with patch("elephant.memory.consolidation.delete_embedded"):
                consolidate_memories([mem_a, mem_b])

    assert not path_a.exists()
    assert not path_b.exists()


# ---------------------------------------------------------------------------
# consolidate_memories — uses highest importance from originals
# ---------------------------------------------------------------------------

def test_consolidate_uses_max_importance(tmp_memories):
    path_a = save_memory("general", "Low Importance", "content A", [], importance=0.3)
    path_b = save_memory("general", "High Importance", "content B", [], importance=0.9)
    mem_a = load_memory(path_a)
    mem_b = load_memory(path_b)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "merged content"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("elephant.memory.consolidation.requests.post", return_value=mock_resp):
        with patch("elephant.memory.consolidation.embed_memory"):
            with patch("elephant.memory.consolidation.delete_embedded"):
                result = consolidate_memories([mem_a, mem_b])

    assert result.metadata.importance == 0.9


# ---------------------------------------------------------------------------
# consolidate_memories — collects tags from all originals
# ---------------------------------------------------------------------------

def test_consolidate_merges_tags(tmp_memories):
    path_a = save_memory("general", "Tagged A", "content A", ["python", "ml"])
    path_b = save_memory("general", "Tagged B", "content B", ["ai", "python"])
    mem_a = load_memory(path_a)
    mem_b = load_memory(path_b)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "merged"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("elephant.memory.consolidation.requests.post", return_value=mock_resp):
        with patch("elephant.memory.consolidation.embed_memory"):
            with patch("elephant.memory.consolidation.delete_embedded"):
                result = consolidate_memories([mem_a, mem_b])

    assert "python" in result.metadata.tags
    assert "ml" in result.metadata.tags
    assert "ai" in result.metadata.tags
