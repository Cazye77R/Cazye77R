"""Find and merge semantically duplicate memories via LLM."""
import logging
from typing import Optional

import requests

from elephant.config import settings
from elephant.memory.markdown_store import (
    delete_memory,
    list_memories,
    load_memory,
    save_memory,
)
from elephant.memory.schemas import Memory
from elephant.memory.vector_store import delete_embedded, embed_memory, search_similar

logger = logging.getLogger(__name__)

MERGE_PROMPT = """\
Fasse die folgenden {n} Memory-Einträge zu einer einzigen, umfassenden Memory zusammen.
Entferne Duplikate, behalte alle wichtigen Informationen. Antworte NUR mit dem zusammengefassten Text.

{entries}"""


def find_consolidation_candidates(
    collection,
    threshold: Optional[float] = None,
) -> list[tuple[Memory, Memory]]:
    """Return pairs of memories with cosine similarity >= threshold.

    Each pair appears only once (order-independent deduplication).
    """
    min_score = threshold if threshold is not None else settings.consolidation_threshold
    memories = [m for m in list_memories() if m.filepath is not None]
    seen: set[frozenset] = set()
    candidates: list[tuple[Memory, Memory]] = []

    for memory in memories:
        query = memory.content[:500]
        results = search_similar(query, top_k=5, collection=collection)

        for r in results:
            other_fp = r["source_file"]
            if other_fp == str(memory.filepath.resolve()):
                continue
            if r["score"] < min_score:
                continue
            key = frozenset([str(memory.filepath.resolve()), other_fp])
            if key in seen:
                continue
            seen.add(key)
            try:
                other = load_memory(other_fp)
                candidates.append((memory, other))
            except Exception:
                pass

    return candidates


def consolidate_memories(
    memories: list[Memory],
    collection=None,
    model: Optional[str] = None,
) -> Memory:
    """Merge *memories* into one via LLM, embed result, delete originals.

    Returns the newly created consolidated Memory.
    """
    llm_model = model or settings.ollama_model
    if not memories:
        raise ValueError("consolidate_memories requires at least one Memory")
    entries = "\n\n---\n\n".join(
        f"### {m.metadata.title}\n\n{m.content}" for m in memories
    )
    prompt = MERGE_PROMPT.format(n=len(memories), entries=entries)

    resp = requests.post(
        f"{settings.ollama_url.rstrip('/')}/api/chat",
        json={"model": llm_model, "messages": [{"role": "user", "content": prompt}], "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    merged_content = resp.json()["message"]["content"]

    max_importance = max(m.metadata.importance for m in memories)
    all_tags = list({tag for m in memories for tag in m.metadata.tags})
    titles = [m.metadata.title for m in memories]
    merged_title = "Konsolidiert: " + " + ".join(titles)[:80]

    categories = [m.category for m in memories if m.category]
    category = max(sorted(set(categories)), key=categories.count) if categories else "general"

    path = save_memory(
        category=category,
        title=merged_title,
        content=merged_content,
        tags=all_tags,
        importance=max_importance,
    )
    logger.info("Consolidated %d memories → %s", len(memories), path.name)

    for m in memories:
        if m.filepath and m.filepath.exists():
            try:
                if collection is not None:
                    delete_embedded(m.filepath, collection=collection)
                delete_memory(m.filepath)
            except Exception as exc:
                logger.warning("Could not delete original %s: %s", m.filepath.name, exc)

    if collection is not None:
        embed_memory(path, collection=collection)

    return load_memory(path)
