"""Unified search interface combining keyword (BM25) and semantic search."""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal

from .index import InvertedIndex, KeywordResult, build_index, search_keyword
from .loader import Chunk
from .semantic import EmbeddingIndex, SemanticResult, build_embedding_index, search_semantic

SearchMode = Literal["keyword", "semantic", "hybrid"]


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    mode: str  # "keyword" | "semantic" | "hybrid"


@dataclass
class SearchIndex:
    keyword_index: InvertedIndex
    embedding_index: EmbeddingIndex | None  # None when semantic=False


def build_search_index(
    chunks: List[Chunk],
    semantic: bool = True,
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    offline: bool = False,
) -> SearchIndex:
    """Build both sub-indexes from the same chunk list."""
    kw_index = build_index(chunks)
    emb_index = (
        build_embedding_index(
            chunks,
            model_name=model_name,
            batch_size=batch_size,
            offline=offline,
        )
        if semantic
        else None
    )
    return SearchIndex(keyword_index=kw_index, embedding_index=emb_index)


def search(
    index: SearchIndex,
    query: str,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
    semantic_weight: float = 0.5,
    offline: bool = False,
) -> List[SearchResult]:
    """
    Run keyword and/or semantic search and return merged, deduplicated results.

    Hybrid: normalize both score lists to [0, 1] then compute
    combined = (1 - semantic_weight) * kw_score + semantic_weight * sem_score.
    """
    if mode == "keyword" or index.embedding_index is None:
        kw_results = search_keyword(index.keyword_index, query, top_k=top_k)
        return [SearchResult(chunk=r.chunk, score=r.score, mode="keyword") for r in kw_results]

    if mode == "semantic":
        sem_results = search_semantic(index.embedding_index, query, top_k=top_k, offline=offline)
        return [SearchResult(chunk=r.chunk, score=r.score, mode="semantic") for r in sem_results]

    # Hybrid: fetch more candidates then merge
    fetch_k = max(top_k * 2, 20)
    kw_results = search_keyword(index.keyword_index, query, top_k=fetch_k)
    sem_results = search_semantic(index.embedding_index, query, top_k=fetch_k, offline=offline)

    kw_map: dict[int, float] = {r.chunk.chunk_id: r.score for r in kw_results}
    sem_map: dict[int, float] = {r.chunk.chunk_id: r.score for r in sem_results}

    kw_map = _minmax(kw_map)
    sem_map = _minmax(sem_map)

    all_ids = set(kw_map) | set(sem_map)
    chunk_by_id = {r.chunk.chunk_id: r.chunk for r in kw_results}
    chunk_by_id.update({r.chunk.chunk_id: r.chunk for r in sem_results})

    combined: list[tuple[int, float]] = []
    for cid in all_ids:
        score = (1 - semantic_weight) * kw_map.get(cid, 0.0) + semantic_weight * sem_map.get(cid, 0.0)
        combined.append((cid, score))

    combined.sort(key=lambda x: x[1], reverse=True)
    return [
        SearchResult(chunk=chunk_by_id[cid], score=score, mode="hybrid")
        for cid, score in combined[:top_k]
    ]


def save_index(index: SearchIndex, path: Path) -> None:
    """Serialize both sub-indexes to a single pickle file."""
    with open(path, "wb") as fh:
        pickle.dump(index, fh)


def load_index(path: Path) -> SearchIndex:
    """Deserialize from pickle."""
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _minmax(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return scores
    lo = min(scores.values())
    hi = max(scores.values())
    span = hi - lo
    if span == 0:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / span for k, v in scores.items()}
