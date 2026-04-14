"""Tests for the BM25 inverted index (index.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from text_search.index import build_index, search_keyword
from text_search.loader import Chunk


def _make_chunks(*texts: str) -> list[Chunk]:
    return [
        Chunk(text=t, source="test.txt", chunk_id=i, page=None, line_start=i + 1)
        for i, t in enumerate(texts)
    ]


def test_build_index_basic():
    """build_index returns an index with correct chunk count and df entries."""
    chunks = _make_chunks("the quick brown fox", "the lazy dog")
    idx = build_index(chunks)
    assert len(idx.chunks) == 2
    assert idx.df["the"] == 2          # appears in both chunks
    assert idx.df["fox"] == 1
    assert idx.avg_dl > 0


def test_search_keyword_ranking():
    """The chunk containing the query term ranks above the one that does not."""
    chunks = _make_chunks(
        "python is a programming language",
        "the weather is nice today",
    )
    idx = build_index(chunks)
    results = search_keyword(idx, "python", top_k=2)
    assert results, "expected at least one result"
    assert results[0].chunk.chunk_id == 0   # python-chunk must be first


def test_search_keyword_empty_query():
    """An empty query returns an empty result list without raising."""
    idx = build_index(_make_chunks("some text here"))
    assert search_keyword(idx, "") == []
    assert search_keyword(idx, "   ") == []


def test_search_keyword_top_k_respected():
    """top_k limits the number of returned results."""
    chunks = _make_chunks(
        "apple fruit",
        "apple juice drink",
        "apple pie baking",
        "apple tree garden",
    )
    idx = build_index(chunks)
    results = search_keyword(idx, "apple", top_k=2)
    assert len(results) <= 2


def test_bm25_scores_positive():
    """All returned BM25 scores must be strictly positive."""
    idx = build_index(_make_chunks("hello world", "hello there", "goodbye world"))
    results = search_keyword(idx, "hello world", top_k=3)
    assert all(r.score > 0 for r in results)
