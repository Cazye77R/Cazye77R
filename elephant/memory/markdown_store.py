from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter

from elephant.config import settings
from elephant.memory.schemas import Memory, MemoryMetadata

CATEGORIES = {"general", "projects", "conversations"}


def _category_path(category: str) -> Path:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category '{category}'. Valid: {CATEGORIES}")
    return settings.memory_path / category


def _slug(title: str) -> str:
    return title.lower().replace(" ", "_").replace("/", "-")


def save_memory(
    category: str,
    title: str,
    content: str,
    tags: list[str],
    importance: float = 0.5,
) -> Path:
    now = datetime.utcnow().isoformat()
    post = frontmatter.Post(
        content,
        title=title,
        tags=tags,
        importance=importance,
        created_at=now,
        updated_at=now,
        last_accessed=now,
    )
    dest = _category_path(category) / f"{_slug(title)}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(frontmatter.dumps(post), encoding="utf-8")
    return dest


def load_memory(filepath: Path | str) -> Memory:
    filepath = Path(filepath)
    post = frontmatter.loads(filepath.read_text(encoding="utf-8"))

    raw_last_accessed = post.get("last_accessed", None)
    if isinstance(raw_last_accessed, str):
        raw_last_accessed = datetime.fromisoformat(raw_last_accessed)

    meta = MemoryMetadata(
        title=post.get("title", filepath.stem),
        tags=post.get("tags", []),
        importance=post.get("importance", 0.5),
        created_at=post.get("created_at", datetime.utcnow()),
        updated_at=post.get("updated_at", datetime.utcnow()),
        last_accessed=raw_last_accessed,
    )
    category = filepath.parent.name if filepath.parent.name in CATEGORIES else None
    return Memory(metadata=meta, content=post.content, filepath=filepath, category=category)


def list_memories(category: Optional[str] = None) -> list[Memory]:
    if category is not None:
        paths = sorted(_category_path(category).glob("*.md"))
    else:
        paths = sorted(settings.memory_path.rglob("*.md"))
    return [load_memory(p) for p in paths]


def search_memories_text(query: str) -> list[Memory]:
    query_lower = query.lower()
    results: list[Memory] = []
    for memory in list_memories():
        haystack = (
            memory.metadata.title
            + " "
            + " ".join(memory.metadata.tags)
            + " "
            + memory.content
        ).lower()
        if query_lower in haystack:
            results.append(memory)
    return results


def delete_memory(filepath: Path | str) -> None:
    Path(filepath).unlink()


def touch_memory(filepath: "Path | str") -> None:
    """Update last_accessed timestamp without changing updated_at."""
    filepath = Path(filepath)
    post = frontmatter.loads(filepath.read_text(encoding="utf-8"))
    post["last_accessed"] = datetime.utcnow().isoformat()
    filepath.write_text(frontmatter.dumps(post), encoding="utf-8")


def update_memory(
    filepath: Path | str,
    content: Optional[str] = None,
    tags: Optional[list[str]] = None,
    importance: Optional[float] = None,
) -> Memory:
    filepath = Path(filepath)
    post = frontmatter.loads(filepath.read_text(encoding="utf-8"))

    if content is not None:
        post.content = content
    if tags is not None:
        post["tags"] = tags
    if importance is not None:
        post["importance"] = importance
    post["updated_at"] = datetime.utcnow().isoformat()

    filepath.write_text(frontmatter.dumps(post), encoding="utf-8")
    return load_memory(filepath)
