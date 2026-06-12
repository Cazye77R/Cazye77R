from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MemoryMetadata(BaseModel):
    title: str
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_accessed: Optional[datetime] = None


class Memory(BaseModel):
    metadata: MemoryMetadata
    content: str
    filepath: Optional[Path] = None
    category: Optional[str] = None
