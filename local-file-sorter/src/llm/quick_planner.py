"""Deterministic quick-planner – bypasses the LLM for well-known sort patterns.

Returns a SortPlan in milliseconds without any Ollama call.
Returns None when the command does not match a known pattern, so the caller
falls through to the full LLM pipeline.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from src.core.scanner import FileInfo
from src.llm.schemas import OpType, SortAction, SortPlan

# ---------------------------------------------------------------------------
# Keyword patterns (German + English) – checked in this order
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

_DATE_PATTERNS = re.compile(
    r"\b(datum|date|jahr|jahre|jahren|monat|monate|monaten|year|years|month|months)\b",
    re.IGNORECASE,
)

_SIZE_PATTERNS = re.compile(
    r"\b(größe|groesse|dateigröße|dateigroesse|size|filesize)\b",
    re.IGNORECASE,
)

_ALPHA_PATTERNS = re.compile(
    r"\b(alphabetisch|alphabetical|namen|by name|nach name)\b",
    re.IGNORECASE,
)

_MONTH_HINT = re.compile(r"\b(monat|monate|monaten|month|months)\b", re.IGNORECASE)

# Folder name for files without an extension
_NO_EXT_FOLDER = "Sonstige"

_SIZE_SMALL_MAX  = 1_048_576      # 1 MB
_SIZE_MEDIUM_MAX = 104_857_600    # 100 MB


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
    if _DATE_PATTERNS.search(cmd):
        granularity = "month" if _MONTH_HINT.search(cmd) else "year"
        return _plan_by_date(files, target_folder, granularity)
    if _SIZE_PATTERNS.search(cmd):
        return _plan_by_size(files, target_folder)
    if _ALPHA_PATTERNS.search(cmd):
        return _plan_alphabetical(files, target_folder)

    return None


# ---------------------------------------------------------------------------
# Shared grouping helper
# ---------------------------------------------------------------------------

def _build_grouped_plan(
    files: list[FileInfo],
    target_folder: Path,
    key_fn: Callable[[FileInfo], str],
    label: str,
) -> SortPlan:
    """Build a SortPlan that groups regular files into folders via key_fn."""
    regular = [f for f in files if not f.is_dir]

    # Collect unique folder names (preserve insertion order via dict)
    seen: dict[str, None] = {}
    for f in regular:
        seen[key_fn(f)] = None

    actions: list[SortAction] = []

    for folder_name in seen:
        actions.append(
            SortAction(
                op_type=OpType.create_folder,
                source=None,
                destination=target_folder / folder_name,
                reason=f"Ordner für {folder_name}",
            )
        )

    for f in regular:
        folder_name = key_fn(f)
        dest = target_folder / folder_name / f.name
        actions.append(
            SortAction(
                op_type=OpType.move,
                source=f.path,
                destination=dest,
                reason=f"{label}: {folder_name}",
            )
        )

    group_list = ", ".join(seen) or "keine"
    return SortPlan(
        actions=actions,
        summary=(
            f"Schnellplan ({label}): {len(regular)} Datei(en) in "
            f"{len(seen)} Ordner sortiert ({group_list})."
        ),
    )


# ---------------------------------------------------------------------------
# Individual planners
# ---------------------------------------------------------------------------

def _plan_by_extension(files: list[FileInfo], target_folder: Path) -> SortPlan:
    return _build_grouped_plan(
        files, target_folder,
        key_fn=lambda f: _ext_to_folder_name(f.extension),
        label="Dateiendung",
    )


def _plan_by_date(
    files: list[FileInfo],
    target_folder: Path,
    granularity: str = "year",
) -> SortPlan:
    if granularity == "month":
        key_fn: Callable[[FileInfo], str] = lambda f: f"{f.modified.year}-{f.modified.month:02d}"
        label = "Monat"
    else:
        key_fn = lambda f: str(f.modified.year)
        label = "Jahr"
    return _build_grouped_plan(files, target_folder, key_fn=key_fn, label=label)


def _plan_by_size(files: list[FileInfo], target_folder: Path) -> SortPlan:
    def key_fn(f: FileInfo) -> str:
        if f.size_bytes < _SIZE_SMALL_MAX:
            return "Klein (unter 1 MB)"
        if f.size_bytes < _SIZE_MEDIUM_MAX:
            return "Mittel (1-100 MB)"
        return "Groß (über 100 MB)"

    return _build_grouped_plan(files, target_folder, key_fn=key_fn, label="Größe")


def _plan_alphabetical(files: list[FileInfo], target_folder: Path) -> SortPlan:
    def key_fn(f: FileInfo) -> str:
        ch = f.name[0].upper() if f.name else ""
        if ch.isalpha():
            return ch
        if ch.isdigit():
            return "0-9"
        return _NO_EXT_FOLDER

    return _build_grouped_plan(files, target_folder, key_fn=key_fn, label="Alphabetisch")
