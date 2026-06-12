"""Exponential importance decay for memories not recently accessed.

Formula: new_importance = max(min_importance, importance * exp(-rate * days_since_accessed))
The reference date is last_accessed if set, otherwise updated_at.
"""
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter

from elephant.config import settings
from elephant.memory.markdown_store import list_memories

logger = logging.getLogger(__name__)
_MIN_IMPORTANCE = 0.05


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _days_since(dt: datetime) -> float:
    delta = _utcnow() - dt.replace(tzinfo=None)
    return max(0.0, delta.total_seconds() / 86400)


def decay_memories(
    decay_rate: Optional[float] = None,
    min_importance: float = _MIN_IMPORTANCE,
    dry_run: bool = False,
) -> dict:
    """Apply exponential decay to all memories.

    Returns {"checked": N, "decayed": N, "skipped": N, "updated_files": [...]}.
    """
    rate = decay_rate if decay_rate is not None else settings.decay_rate
    memories = list_memories()
    decayed = 0
    skipped = 0
    updated: list[str] = []

    for memory in memories:
        if memory.filepath is None:
            skipped += 1
            continue

        meta = memory.metadata
        reference_dt = meta.last_accessed or meta.updated_at
        days = _days_since(reference_dt)

        if days < 1.0:
            skipped += 1
            continue

        old_imp = meta.importance
        new_imp = round(max(min_importance, old_imp * math.exp(-rate * days)), 4)

        if abs(new_imp - old_imp) < 0.001:
            skipped += 1
            continue

        if not dry_run:
            try:
                post = frontmatter.loads(memory.filepath.read_text(encoding="utf-8"))
                post["importance"] = new_imp
                memory.filepath.write_text(frontmatter.dumps(post), encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not decay %s: %s", memory.filepath.name, exc)
                skipped += 1
                continue

        logger.info(
            "Decayed %s: %.3f → %.3f (%.1f days)",
            memory.filepath.name, old_imp, new_imp, days,
        )
        decayed += 1
        updated.append(str(memory.filepath))

    return {"checked": len(memories), "decayed": decayed, "skipped": skipped, "updated_files": updated}
