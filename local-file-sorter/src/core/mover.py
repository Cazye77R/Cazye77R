from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from pydantic import BaseModel

_DUPLICATE_FOLDER = "_Duplikate"
_HASH_CHUNK_SIZE  = 1024 * 1024   # 1 MB
_HASH_SIZE_LIMIT  = 200 * 1024 * 1024  # skip hashing (treat as non-duplicate) above 200 MB


class MoveResult(BaseModel):
    success: bool
    source_original: Path
    destination_final: Path
    error: str | None = None
    is_duplicate: bool = False

    model_config = {"arbitrary_types_allowed": True}


def resolve_conflict(destination: Path) -> Path:
    """Return a non-colliding path by appending _1, _2, … to the stem."""
    if not destination.exists():
        return destination
    stem   = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def is_duplicate(source: Path, existing: Path) -> bool:
    """True if *source* and *existing* have identical size and content.

    Skips the (expensive) content hash for very large files and returns
    False in that case — better to fall back to a safe rename than to hang
    on multi-GB files.
    """
    try:
        size_a = source.stat().st_size
        size_b = existing.stat().st_size
        if size_a != size_b:
            return False
        if size_a > _HASH_SIZE_LIMIT:
            return False
        return _hash_file(source) == _hash_file(existing)
    except OSError:
        return False


def move_file(source: Path, destination: Path) -> MoveResult:
    if not source.exists():
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=destination,
            error=f"Quelldatei existiert nicht: {source}",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    duplicate = False
    if destination.exists():
        if is_duplicate(source, destination):
            duplicate = True
            dup_dir = destination.parent / _DUPLICATE_FOLDER
            dup_dir.mkdir(parents=True, exist_ok=True)
            final_destination = resolve_conflict(dup_dir / destination.name)
        else:
            final_destination = resolve_conflict(destination)
    else:
        final_destination = destination

    try:
        shutil.move(str(source), str(final_destination))
        return MoveResult(
            success=True,
            source_original=source,
            destination_final=final_destination,
            is_duplicate=duplicate,
        )
    except PermissionError as exc:
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=final_destination,
            error=f"Zugriff verweigert (Datei gesperrt?): {exc}",
            is_duplicate=duplicate,
        )
    except OSError as exc:
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=final_destination,
            error=f"Dateisystem-Fehler: {exc}",
            is_duplicate=duplicate,
        )
    except Exception as exc:
        return MoveResult(
            success=False,
            source_original=source,
            destination_final=final_destination,
            error=str(exc),
            is_duplicate=duplicate,
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
