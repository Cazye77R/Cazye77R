"""BM25 inverted index for fast keyword search."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from .loader import Chunk


@dataclass
class KeywordResult:
    chunk: Chunk
    score: float


@dataclass
class InvertedIndex:
    chunks: List[Chunk]
    df: Dict[str, int]          # document frequency per term
    tf: List[Dict[str, int]]    # term frequency per chunk
    avg_dl: float               # average document length in tokens
    doc_lengths: List[int]      # token count per chunk — precomputed for O(1) BM25 lookup
    k1: float = 1.5
    b: float = 0.75


def build_index(chunks: List[Chunk]) -> InvertedIndex:
    """Tokenize all chunks and compute BM25 statistics."""
    tf: List[Dict[str, int]] = []
    df: Dict[str, int] = defaultdict(int)
    total_len = 0

    for chunk in chunks:
        tokens = _tokenize(chunk.text)
        total_len += len(tokens)
        freq: Dict[str, int] = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        tf.append(dict(freq))
        for term in freq:
            df[term] += 1

    avg_dl = total_len / len(chunks) if chunks else 1.0
    doc_lengths = [sum(tf_doc.values()) for tf_doc in tf]
    return InvertedIndex(chunks=chunks, df=dict(df), tf=tf, avg_dl=avg_dl, doc_lengths=doc_lengths)


def search_keyword(
    index: InvertedIndex,
    query: str,
    top_k: int = 10,
) -> List[KeywordResult]:
    """Score every relevant chunk with BM25 and return the top_k results."""
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    n = len(index.chunks)
    scores: Dict[int, float] = {}

    for term in set(query_terms):
        df_t = index.df.get(term, 0)
        if df_t == 0:
            continue
        idf = math.log((n - df_t + 0.5) / (df_t + 0.5) + 1)

        for doc_id, tf_doc in enumerate(index.tf):
            tf_t = tf_doc.get(term, 0)
            if tf_t == 0:
                continue
            dl = index.doc_lengths[doc_id]
            numerator = tf_t * (index.k1 + 1)
            denominator = tf_t + index.k1 * (1 - index.b + index.b * dl / index.avg_dl)
            scores[doc_id] = scores.get(doc_id, 0.0) + idf * numerator / denominator

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [KeywordResult(chunk=index.chunks[doc_id], score=score) for doc_id, score in ranked]


def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return re.sub(r"[^\w\s]", " ", text).lower().split()
