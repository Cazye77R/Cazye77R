"""Deterministic quick-planner – bypasses the LLM for well-known sort patterns.

Returns a SortPlan in milliseconds without any Ollama call.
Returns None when the command does not match a known pattern, so the caller
falls through to the full LLM pipeline.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.core.scanner import FileInfo
from src.llm.schemas import OpType, SortAction, SortPlan

# ---------------------------------------------------------------------------
# Keyword patterns (German + English)
# ---------------------------------------------------------------------------

_EXT_PATTERNS = re.compile(
    r"\b("
    r"endung|endungen|dateiendung|dateiendungen"
    r"|extension|extensions|ext"
    r"|typ|typen|dateityp|dateitypen|file.?type"
    r"|format|formate"
    r")\b",
    re.IGNORECASE,
)

# Folder name for files without an extension
_NO_EXT_FOLDER = "Sonstige"


def _ext_to_folder_name(ext: str) -> str:
    """Convert a dot-extension like '.pdf' → 'PDF'."""
    return ext.lstrip(".").upper() if ext else _NO_EXT_FOLDER


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def try_quick_plan(
    command: str,
    files: list[FileInfo],
    target_folder: Path,
) -> SortPlan | None:
    """Return a SortPlan instantly if *command* matches a known pattern.

    Returns None when the command is not recognised — the caller should then
    use the LLM pipeline.
    """
    cmd = command.strip()

    if _EXT_PATTERNS.search(cmd):
        return _plan_by_extension(files, target_folder)

    return None


# ---------------------------------------------------------------------------
# Extension-based planner
# ---------------------------------------------------------------------------

def _plan_by_extension(files: list[FileInfo], target_folder: Path) -> SortPlan:
    # Only regular files (not directories)
    regular = [f for f in files if not f.is_dir]

    # Collect unique extensions (preserve insertion order via dict)
    seen: dict[str, None] = {}
    for f in regular:
        seen[f.extension] = None

    actions: list[SortAction] = []

    # 1. create_folder actions (one per unique extension)
    for ext in seen:
        folder_name = _ext_to_folder_name(ext)
        folder_path = target_folder / folder_name
        actions.append(
            SortAction(
                op_type=OpType.create_folder,
                source=None,
                destination=folder_path,
                reason=f"Ordner für {folder_name}-Dateien",
            )
        )

    # 2. move actions
    for f in regular:
        folder_name = _ext_to_folder_name(f.extension)
        dest = target_folder / folder_name / f.name
        actions.append(
            SortAction(
                op_type=OpType.move,
                source=f.path,
                destination=dest,
                reason=f"{f.extension or '(kein)'} → {folder_name}/",
            )
        )

    ext_list = ", ".join(
        _ext_to_folder_name(e) for e in seen
    ) or "keine"

    return SortPlan(
        actions=actions,
        summary=(
            f"Schnellplan: {len(regular)} Datei(en) in "
            f"{len(seen)} Ordner sortiert ({ext_list})."
        ),
    )
