from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator


class OpType(str, Enum):
    move = "move"
    create_folder = "create_folder"


class SortAction(BaseModel):
    op_type: OpType
    source: Path | None = None
    destination: Path
    reason: str

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("destination", "source", mode="before")
    @classmethod
    def _normalize_path(cls, v: object) -> object:
        if isinstance(v, str) and v:
            # LLM on Windows sometimes outputs \C:\path instead of C:\path.
            # Strip any leading backslashes before a drive letter (e.g. \C:\ → C:\).
            v = re.sub(r'^\\+([A-Za-z]:[\\])', r'\1', v)
        return v


class SortPlan(BaseModel):
    actions: list[SortAction]
    summary: str

    @model_validator(mode="after")
    def only_allowed_ops(self) -> "SortPlan":
        allowed = {OpType.move, OpType.create_folder}
        bad = [a for a in self.actions if a.op_type not in allowed]
        if bad:
            types = ", ".join(str(b.op_type) for b in bad)
            raise ValueError(
                f"Plan enthält verbotene Operationen ({types}). "
                "Nur 'move' und 'create_folder' sind erlaubt."
            )
        return self
