from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class MemoryMetadata(BaseModel):
    title: str
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Memory(BaseModel):
    metadata: MemoryMetadata
    content: str
    filepath: Optional[Path] = None
    category: Optional[str] = None
