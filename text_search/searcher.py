"""Unified search interface combining keyword (BM25) and semantic search."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal

from .index import InvertedIndex, KeywordResult, build_index, search_keyword
from .loader import Chunk
from .semantic import EmbeddingIndex, SemanticResult, build_embedding_index, search_semantic

SearchMode = Literal["keyword", "semantic", "hybrid"]

_RRF_K = 60  # RRF damping constant — standard value from Cormack et al. 2009


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
        return deduplicate_results(
            [SearchResult(chunk=r.chunk, score=r.score, mode="keyword") for r in kw_results]
        )

    if mode == "semantic":
        sem_results = search_semantic(index.embedding_index, query, top_k=top_k, offline=offline)
        return deduplicate_results(
            [SearchResult(chunk=r.chunk, score=r.score, mode="semantic") for r in sem_results]
        )

    # Hybrid: Reciprocal Rank Fusion (RRF)
    # RRF score = Σ weight_i / (k + rank_i)  where k=60 dampens the impact of
    # top ranks and prevents a single dominant list from overwhelming the other.
    # Using rank position (not raw scores) makes fusion robust across differently
    # scaled retrievers (BM25 values vs. cosine similarity in [0, 1]).
    fetch_k = max(top_k * 2, 20)
    kw_results = search_keyword(index.keyword_index, query, top_k=fetch_k)
    sem_results = search_semantic(index.embedding_index, query, top_k=fetch_k, offline=offline)

    chunk_by_id: dict[int, Chunk] = {r.chunk.chunk_id: r.chunk for r in kw_results}
    chunk_by_id.update({r.chunk.chunk_id: r.chunk for r in sem_results})

    kw_weight  = 1.0 - semantic_weight
    sem_weight = semantic_weight

    # Build rank-position maps so each chunk's contribution from both methods
    # can be computed explicitly in a single pass.
    kw_ranks:  dict[int, int] = {r.chunk.chunk_id: rank for rank, r in enumerate(kw_results,  1)}
    sem_ranks: dict[int, int] = {r.chunk.chunk_id: rank for rank, r in enumerate(sem_results, 1)}

    rrf_scores: dict[int, float] = {}
    for cid in chunk_by_id:
        # Chunks absent from one pool get 0.0 from that method — explicit, not implicit.
        kw_contrib  = kw_weight  / (_RRF_K + kw_ranks[cid])  if cid in kw_ranks  else 0.0
        sem_contrib = sem_weight / (_RRF_K + sem_ranks[cid]) if cid in sem_ranks else 0.0
        rrf_scores[cid] = kw_contrib + sem_contrib

    combined = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return deduplicate_results([
        SearchResult(chunk=chunk_by_id[cid], score=score, mode="hybrid")
        for cid, score in combined[:top_k]
    ])


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """Remove near-duplicate chunks from the same source file.

    Iterates results in score order (highest first) and skips any result
    whose chunk_id is within 1 of an already-accepted chunk from the same
    source. This prevents overlapping sentence-window chunks from flooding
    the top results.
    """
    accepted: list[SearchResult] = []
    seen: dict[str, list[int]] = {}  # source → accepted chunk_ids

    for r in results:
        source = r.chunk.source
        accepted_ids = seen.get(source, [])
        if any(abs(r.chunk.chunk_id - aid) < 2 for aid in accepted_ids):
            continue
        accepted.append(r)
        seen.setdefault(source, []).append(r.chunk.chunk_id)

    return accepted


def save_index(index: SearchIndex, path: Path) -> None:
    """Serialize the index to a ZIP file — safe, no pickle.

    Archive layout:
      bm25.json      — BM25 statistics + chunk metadata (JSON, human-readable)
      embeddings.npy — embedding matrix as raw float32 numpy array (if present)
      meta.json      — format version + model name
    """
    import numpy as np

    bm25_payload = {
        "k1": index.keyword_index.k1,
        "b": index.keyword_index.b,
        "avg_dl": index.keyword_index.avg_dl,
        "df": index.keyword_index.df,
        "tf": index.keyword_index.tf,
        "chunks": [
            {
                "text": c.text,
                "source": c.source,
                "chunk_id": c.chunk_id,
                "page": c.page,
                "line_start": c.line_start,
            }
            for c in index.keyword_index.chunks
        ],
    }
    has_emb = index.embedding_index is not None
    meta_payload = {
        "format_version": 1,
        "has_embeddings": has_emb,
        "model_name": index.embedding_index.model_name if has_emb else None,
    }

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bm25.json", json.dumps(bm25_payload, ensure_ascii=False))
        zf.writestr("meta.json", json.dumps(meta_payload))
        if has_emb:
            buf = io.BytesIO()
            np.save(buf, index.embedding_index.embeddings.numpy())  # type: ignore[union-attr]
            zf.writestr("embeddings.npy", buf.getvalue())


def load_index(path: Path) -> SearchIndex:
    """Deserialize from a ZIP file created by save_index. No pickle, no code execution."""
    import numpy as np
    import torch

    with zipfile.ZipFile(path, "r") as zf:
        bm25_data = json.loads(zf.read("bm25.json"))
        meta = json.loads(zf.read("meta.json"))

        chunks = [
            Chunk(
                text=c["text"],
                source=c["source"],
                chunk_id=c["chunk_id"],
                page=c.get("page"),
                line_start=c.get("line_start"),
            )
            for c in bm25_data["chunks"]
        ]

        kw_index = InvertedIndex(
            chunks=chunks,
            df=bm25_data["df"],
            tf=[{k: v for k, v in tf.items()} for tf in bm25_data["tf"]],
            avg_dl=bm25_data["avg_dl"],
            k1=bm25_data["k1"],
            b=bm25_data["b"],
        )

        emb_index = None
        if meta.get("has_embeddings"):
            from .semantic import EmbeddingIndex
            buf = io.BytesIO(zf.read("embeddings.npy"))
            emb_np = np.load(buf, allow_pickle=False)
            emb_index = EmbeddingIndex(
                chunks=chunks,
                embeddings=torch.from_numpy(emb_np),
                model_name=meta["model_name"],
            )

        return SearchIndex(keyword_index=kw_index, embedding_index=emb_index)


