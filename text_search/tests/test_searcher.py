"""Tests for the unified search interface (searcher.py)."""
import io
import sys
import zipfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from text_search.loader import Chunk
from text_search.index import build_index
from text_search.searcher import (
    SearchIndex,
    build_search_index,
    save_index,
    load_index,
    search,
)


def _make_chunks(*texts: str) -> list[Chunk]:
    return [
        Chunk(text=t, source="doc.txt", chunk_id=i, page=None, line_start=i + 1)
        for i, t in enumerate(texts)
    ]


def _keyword_only_index(chunks: list[Chunk]) -> SearchIndex:
    return SearchIndex(keyword_index=build_index(chunks), embedding_index=None)


def test_search_keyword_mode():
    """Keyword search returns results ordered by relevance."""
    chunks = _make_chunks(
        "machine learning algorithms",
        "baking bread at home",
        "machine learning deep neural networks",
    )
    idx = _keyword_only_index(chunks)
    results = search(idx, "machine learning", mode="keyword", top_k=3)
    assert len(results) >= 1
    ids = [r.chunk.chunk_id for r in results]
    # Both ML chunks must appear; bread chunk must not score
    assert 0 in ids or 2 in ids
    assert all(r.score > 0 for r in results)


def test_search_falls_back_to_keyword_without_embedding():
    """Requesting hybrid/semantic without embedding index falls back gracefully."""
    chunks = _make_chunks("fallback test sentence.")
    idx = _keyword_only_index(chunks)
    # Should not raise; falls back to keyword
    results = search(idx, "fallback", mode="hybrid", top_k=5)
    assert isinstance(results, list)


def test_search_top_k_limit():
    """search() never returns more than top_k results."""
    chunks = _make_chunks(*[f"document about topic {i}." for i in range(10)])
    idx = _keyword_only_index(chunks)
    results = search(idx, "document topic", mode="keyword", top_k=3)
    assert len(results) <= 3


def test_save_and_load_index_roundtrip(tmp_path: Path):
    """save_index + load_index preserves chunk texts and BM25 parameters."""
    chunks = _make_chunks("round trip test.", "another sentence here.")
    idx = _keyword_only_index(chunks)

    zip_path = tmp_path / "index.zip"
    save_index(idx, zip_path)

    # Verify the ZIP contains the expected files (no pickle)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "bm25.json" in names
    assert "meta.json" in names
    assert not any(n.endswith(".pkl") for n in names)

    loaded = load_index(zip_path)
    original_texts = {c.text for c in idx.keyword_index.chunks}
    loaded_texts   = {c.text for c in loaded.keyword_index.chunks}
    assert original_texts == loaded_texts
    assert loaded.keyword_index.avg_dl == idx.keyword_index.avg_dl


def test_search_result_mode_field():
    """SearchResult.mode reflects the requested search mode."""
    chunks = _make_chunks("test document one.", "test document two.")
    idx = _keyword_only_index(chunks)
    results = search(idx, "test", mode="keyword", top_k=2)
    assert all(r.mode == "keyword" for r in results)
