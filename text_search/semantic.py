"""Semantic search via sentence-transformer embeddings and cosine similarity."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import List

import torch

# Set HuggingFace cache to a user-writable location BEFORE sentence_transformers
# is imported (the library reads these paths at import time, not at model-load time).
# Uses ~/hf_cache which is always writable on all platforms including Windows.
_HF_CACHE = str(_Path.home() / "hf_cache")
os.environ.setdefault("HF_HOME", _HF_CACHE)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _HF_CACHE)
os.environ.setdefault("HF_HUB_CACHE", str(_Path(_HF_CACHE) / "hub"))

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
    offline: bool = False,
) -> EmbeddingIndex:
    """Encode all chunk texts and return a normalized embedding matrix."""
    model = _get_model(model_name, offline=offline)
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
    offline: bool = False,
) -> List[SemanticResult]:
    """Embed query and return top_k chunks by cosine similarity."""
    model = _get_model(index.model_name, offline=offline)
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
    # cos_sim returns -1..1, clamp to 0..1 for fair hybrid weighting
    return [SemanticResult(chunk=index.chunks[i], score=max(0.0, float(s))) for i, s in ranked]


def _get_model(model_name: str, offline: bool = False) -> object:
    """Return a cached SentenceTransformer instance.

    Sets or clears TRANSFORMERS_OFFLINE / HF_DATASETS_OFFLINE on every call
    so that toggling offline=False after a prior offline=True call actually
    re-enables network access (os.environ.setdefault would have left the vars
    set permanently for the process lifetime).
    """
    if offline:
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
    else:
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
        os.environ.pop("HF_DATASETS_OFFLINE", None)
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def _default_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"
