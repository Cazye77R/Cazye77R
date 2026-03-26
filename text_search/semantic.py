"""Semantic search via sentence-transformer embeddings and cosine similarity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import torch

from .loader import Chunk

# Module-level model cache — avoids reloading between non-Streamlit calls
_MODEL_CACHE: dict[str, object] = {}

DEFAULT_MODEL = "all-MiniLM-L6-v2"


@dataclass
class SemanticResult:
    chunk: Chunk
    score: float  # cosine similarity in [0, 1]


@dataclass
class EmbeddingIndex:
    chunks: List[Chunk]
    embeddings: torch.Tensor  # shape [N, D], float32, L2-normalized
    model_name: str = DEFAULT_MODEL


def build_embedding_index(
    chunks: List[Chunk],
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 64,
    device: str | None = None,
) -> EmbeddingIndex:
    """Encode all chunk texts and return a normalized embedding matrix."""
    model = _get_model(model_name)
    texts = [c.text for c in chunks]
    embeddings: torch.Tensor = model.encode(  # type: ignore[attr-defined]
        texts,
        batch_size=batch_size,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        device=device or _default_device(),
    )
    return EmbeddingIndex(chunks=chunks, embeddings=embeddings.cpu(), model_name=model_name)


def search_semantic(
    index: EmbeddingIndex,
    query: str,
    top_k: int = 10,
    device: str | None = None,
) -> List[SemanticResult]:
    """Embed query and return top_k chunks by cosine similarity."""
    model = _get_model(index.model_name)
    query_vec: torch.Tensor = model.encode(  # type: ignore[attr-defined]
        [query],
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        device=device or _default_device(),
    )
    query_vec = query_vec.cpu().squeeze(0)  # [D]

    scores = (index.embeddings @ query_vec).tolist()  # [N]
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [SemanticResult(chunk=index.chunks[i], score=float(s)) for i, s in ranked]


def _get_model(model_name: str) -> object:
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def _default_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"
