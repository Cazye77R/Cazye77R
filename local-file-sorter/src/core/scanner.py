from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, field_validator


class FileInfo(BaseModel):
    path: Path
    name: str
    extension: str
    size_bytes: int
    created: datetime
    modified: datetime
    is_dir: bool

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("path", mode="before")
    @classmethod
    def coerce_path(cls, v: object) -> Path:
        return Path(v)  # type: ignore[arg-type]


def _is_hidden(p: Path) -> bool:
    return p.name.startswith(".")


def _make_file_info(p: Path) -> FileInfo:
    stat = p.stat()
    return FileInfo(
        path=p.resolve(),
        name=p.name,
        extension=p.suffix.lower(),
        size_bytes=stat.st_size,
        created=datetime.fromtimestamp(stat.st_ctime),
        modified=datetime.fromtimestamp(stat.st_mtime),
        is_dir=p.is_dir(),
    )


def scan_folder(path: Path, recursive: bool = False) -> list[FileInfo]:
    root = Path(path)
    if not root.is_dir():
        raise NotADirectoryError(f"{root} ist kein Verzeichnis")

    results: list[FileInfo] = []

    if recursive:
        entries = root.rglob("*")
    else:
        entries = root.iterdir()

    for entry in entries:
        if entry.is_symlink():
            continue
        if _is_hidden(entry):
            continue
        try:
            results.append(_make_file_info(entry))
        except (PermissionError, OSError):
            continue

    return results
