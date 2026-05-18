from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel


class MoveResult(BaseModel):
    success: bool
    source_original: Path
    destination_final: Path
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def _resolve_conflict(destination: Path) -> Path:
    if not destination.exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_file(source: Path, destination: Path) -> MoveResult:
    if not source.exists():
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=destination,
            error=f"Quelldatei existiert nicht: {source}",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    final_destination = _resolve_conflict(destination)

    try:
        shutil.move(str(source), str(final_destination))
        return MoveResult(
            success=True,
            source_original=source,
            destination_final=final_destination,
        )
    except Exception as exc:
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=final_destination,
            error=str(exc),
        )


def create_folder(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def is_safe_destination(destination: Path, allowed_root: Path) -> bool:
    try:
        resolved_dest = destination.resolve()
        resolved_root = allowed_root.resolve()
        resolved_dest.relative_to(resolved_root)
        return True
    except ValueError:
        return False
