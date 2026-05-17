import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import chromadb
import requests
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from elephant.config import settings
from elephant.memory.markdown_store import list_memories, load_memory

EMBEDDING_MODEL = "nomic-embed-text"
CHUNK_TOKEN_LIMIT = 500
CHUNK_OVERLAP_TOKENS = 50
_CHARS_PER_TOKEN = 4  # rough approximation; 1 token ≈ 4 characters

_collection: Optional[chromadb.Collection] = None


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB EmbeddingFunction that proxies requests to Ollama.

    Inherits from EmbeddingFunction[Documents] to satisfy the full Protocol
    required by chromadb >= 1.0, including embed_query() and is_legacy().
    """

    def __init__(self, model: str = EMBEDDING_MODEL, base_url: Optional[str] = None):
        self.model = model
        self.base_url = (base_url or settings.ollama_url).rstrip("/")

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60,
            )
            response.raise_for_status()
            embeddings.append(response.json()["embedding"])
        return embeddings

    @staticmethod
    def name() -> str:
        return "ollama-embedding-function"

    @staticmethod
    def build_from_config(config: dict) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(
            model=config.get("model", EMBEDDING_MODEL),
            base_url=config.get("base_url"),
        )

    def get_config(self) -> dict:
        return {"model": self.model, "base_url": self.base_url}


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def init_collection(
    chroma_client: Optional[chromadb.ClientAPI] = None,
) -> chromadb.Collection:
    """Create or load the persistent ChromaDB collection.

    Pass a *chroma_client* (e.g. ``chromadb.EphemeralClient()``) to override
    the default PersistentClient — useful in tests.
    """
    global _collection
    if chroma_client is None:
        chroma_path = settings.memories_base_path.parent.parent / "chromadb"
        chroma_path.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=str(chroma_path))

    embedding_fn = OllamaEmbeddingFunction()
    _collection = chroma_client.get_or_create_collection(
        name="memories",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        init_collection()
    return _collection


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(title: str, content: str) -> list[str]:
    """Split *content* into chunks of ~CHUNK_TOKEN_LIMIT tokens with overlap.

    Each chunk is prefixed with the memory title so retrieval context is
    self-contained.
    """
    limit_chars = CHUNK_TOKEN_LIMIT * _CHARS_PER_TOKEN
    overlap_chars = CHUNK_OVERLAP_TOKENS * _CHARS_PER_TOKEN

    paragraphs = [p.strip() for p in re.split(r"\n\n+", content) if p.strip()]
    if not paragraphs:
        stripped = content.strip()
        return [f"# {title}\n\n{stripped}"] if stripped else []

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        if current_parts and current_len + para_len > limit_chars:
            # Emit the current chunk
            chunks.append(f"# {title}\n\n" + "\n\n".join(current_parts))

            # Carry over trailing paragraphs that fit within the overlap budget
            overlap_parts: list[str] = []
            overlap_len = 0
            for part in reversed(current_parts):
                if overlap_len + len(part) <= overlap_chars:
                    overlap_parts.insert(0, part)
                    overlap_len += len(part)
                else:
                    break

            current_parts = overlap_parts + [para]
            current_len = overlap_len + para_len
        else:
            current_parts.append(para)
            current_len += para_len

    if current_parts:
        chunks.append(f"# {title}\n\n" + "\n\n".join(current_parts))

    return chunks or [f"# {title}\n\n{content}"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_key(filepath: Path) -> str:
    """Stable string key stored as source_file metadata."""
    return str(filepath.resolve())


def _id_prefix(filepath: Path) -> str:
    return hashlib.md5(_source_key(filepath).encode()).hexdigest()[:16]


def _delete_by_source(coll: chromadb.Collection, source_file: str) -> None:
    results = coll.get(where={"source_file": source_file})
    if results["ids"]:
        coll.delete(ids=results["ids"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_memory(
    filepath: "Path | str",
    collection: Optional[chromadb.Collection] = None,
) -> int:
    """Load a Markdown file, chunk it, and upsert into ChromaDB.

    Returns the number of chunks stored.
    """
    filepath = Path(filepath)
    coll = collection or _get_collection()
    memory = load_memory(filepath)
    source = _source_key(filepath)

    # Remove stale embeddings before (re-)inserting
    _delete_by_source(coll, source)

    chunks = _chunk_text(memory.metadata.title, memory.content)
    if not chunks:
        return 0

    prefix = _id_prefix(filepath)
    ids = [f"{prefix}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_file": source,
            "category": memory.category or "",
            "title": memory.metadata.title,
            "tags": json.dumps(memory.metadata.tags),
            "importance": memory.metadata.importance,
            "updated_at": memory.metadata.updated_at.isoformat(),
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    coll.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def sync_all_memories(
    collection: Optional[chromadb.Collection] = None,
) -> dict[str, int]:
    """Embed all Markdown files, skipping ones whose updated_at hasn't changed.

    Returns ``{"synced": N, "skipped": M, "total": N+M}``.
    """
    coll = collection or _get_collection()
    synced = skipped = 0

    for memory in list_memories():
        if memory.filepath is None:
            continue
        source = _source_key(memory.filepath)
        file_ts = memory.metadata.updated_at.isoformat()

        existing = coll.get(where={"source_file": source}, limit=1)
        if existing["ids"] and existing["metadatas"][0].get("updated_at") == file_ts:
            skipped += 1
            continue

        embed_memory(memory.filepath, collection=coll)
        synced += 1

    return {"synced": synced, "skipped": skipped, "total": synced + skipped}


def search_similar(
    query: str,
    top_k: int = 5,
    min_importance: float = 0.0,
    category_filter: Optional[str] = None,
    collection: Optional[chromadb.Collection] = None,
) -> list[dict]:
    """Semantic search; returns chunks sorted by cosine similarity (highest first).

    Each result dict has keys: ``chunk``, ``metadata``, ``score``, ``source_file``.
    """
    coll = collection or _get_collection()

    count = coll.count()
    if count == 0:
        return []

    # Build where clause
    conditions: list[dict] = []
    if min_importance > 0.0:
        conditions.append({"importance": {"$gte": min_importance}})
    if category_filter:
        conditions.append({"category": category_filter})

    where: Optional[dict] = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    query_kwargs: dict = {
        "query_texts": [query],
        "n_results": min(top_k, count),
    }
    if where is not None:
        query_kwargs["where"] = where

    try:
        results = coll.query(**query_kwargs)
    except Exception:
        # ChromaDB raises when n_results > number of docs that satisfy the where
        # clause.  Retry with n_results=1 to get at least the best match.
        query_kwargs["n_results"] = 1
        try:
            results = coll.query(**query_kwargs)
        except Exception:
            return []

    output: list[dict] = []
    for i, _ in enumerate(results["ids"][0]):
        distance = results["distances"][0][i] if results.get("distances") else 0.0
        raw_meta = dict(results["metadatas"][0][i]) if results.get("metadatas") else {}
        try:
            raw_meta["tags"] = json.loads(raw_meta.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass
        output.append(
            {
                "chunk": results["documents"][0][i] if results.get("documents") else "",
                "metadata": raw_meta,
                "score": round(1.0 - distance, 6),
                "source_file": raw_meta.get("source_file", ""),
            }
        )
    return output


def delete_embedded(
    filepath: "Path | str",
    collection: Optional[chromadb.Collection] = None,
) -> None:
    """Remove all chunks of *filepath* from ChromaDB."""
    coll = collection or _get_collection()
    _delete_by_source(coll, _source_key(Path(filepath)))
