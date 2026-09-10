"""Tests for the deterministic quick-planner (no LLM required)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.core.scanner import FileInfo
from src.llm.quick_planner import try_quick_plan, _ext_to_folder_name
from src.llm.schemas import OpType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(name: str, folder: Path) -> FileInfo:
    suffix = Path(name).suffix.lower()
    return FileInfo(
        path=folder / name,
        name=name,
        extension=suffix,
        size_bytes=1024,
        created=datetime(2024, 1, 1),
        modified=datetime(2024, 1, 1),
        is_dir=False,
    )


def _make_dir(name: str, folder: Path) -> FileInfo:
    return FileInfo(
        path=folder / name,
        name=name,
        extension="",
        size_bytes=0,
        created=datetime(2024, 1, 1),
        modified=datetime(2024, 1, 1),
        is_dir=True,
    )


TARGET = Path("/tmp/target")
FILES = [
    _make_file("report.pdf", TARGET),
    _make_file("photo.jpg", TARGET),
    _make_file("notes.txt", TARGET),
    _make_file("data.csv", TARGET),
    _make_file("image.jpg", TARGET),
]


# ---------------------------------------------------------------------------
# Keyword detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "Sortiere nach Dateiendung",
    "sort by extension",
    "Dateien nach Endung sortieren",
    "bitte nach Dateityp organisieren",
    "group by file type",
    "Sortiere nach Format",
    "sort by ext",
])
def test_recognised_commands(cmd: str) -> None:
    plan = try_quick_plan(cmd, FILES, TARGET)
    assert plan is not None, f"Expected quick plan for: {cmd!r}"


@pytest.mark.parametrize("cmd", [
    "älteste Dateien zuerst",
    "wichtigste zuerst",
    "Bilder nach Inhalt sortieren",
    "räume auf",
])
def test_unrecognised_commands_return_none(cmd: str) -> None:
    plan = try_quick_plan(cmd, FILES, TARGET)
    assert plan is None, f"Expected None for: {cmd!r}"


# ---------------------------------------------------------------------------
# Date-based planner
# ---------------------------------------------------------------------------

def _dated_files() -> list[FileInfo]:
    return [
        FileInfo(path=TARGET / "a.txt", name="a.txt", extension=".txt",
                 size_bytes=100, created=datetime(2024, 3, 5), modified=datetime(2024, 3, 5),
                 is_dir=False),
        FileInfo(path=TARGET / "b.txt", name="b.txt", extension=".txt",
                 size_bytes=100, created=datetime(2024, 11, 20), modified=datetime(2024, 11, 20),
                 is_dir=False),
        FileInfo(path=TARGET / "c.txt", name="c.txt", extension=".txt",
                 size_bytes=100, created=datetime(2025, 1, 2), modified=datetime(2025, 1, 2),
                 is_dir=False),
    ]


@pytest.mark.parametrize("cmd", [
    "sortiere nach Datum", "sort by date", "nach Jahr sortieren", "sort by year",
])
def test_date_year_recognised(cmd: str) -> None:
    plan = try_quick_plan(cmd, _dated_files(), TARGET)
    assert plan is not None
    folders = {a.destination.name for a in plan.actions if a.op_type == OpType.create_folder}
    assert folders == {"2024", "2025"}


@pytest.mark.parametrize("cmd", ["nach Monat sortieren", "sort by month"])
def test_date_month_granularity(cmd: str) -> None:
    plan = try_quick_plan(cmd, _dated_files(), TARGET)
    assert plan is not None
    folders = {a.destination.name for a in plan.actions if a.op_type == OpType.create_folder}
    assert folders == {"2024-03", "2024-11", "2025-01"}


# ---------------------------------------------------------------------------
# Size-based planner
# ---------------------------------------------------------------------------

def _sized_files() -> list[FileInfo]:
    return [
        FileInfo(path=TARGET / "small.txt", name="small.txt", extension=".txt",
                 size_bytes=500, created=datetime(2024, 1, 1), modified=datetime(2024, 1, 1),
                 is_dir=False),
        FileInfo(path=TARGET / "mid.bin", name="mid.bin", extension=".bin",
                 size_bytes=10_000_000, created=datetime(2024, 1, 1), modified=datetime(2024, 1, 1),
                 is_dir=False),
        FileInfo(path=TARGET / "big.iso", name="big.iso", extension=".iso",
                 size_bytes=500_000_000, created=datetime(2024, 1, 1), modified=datetime(2024, 1, 1),
                 is_dir=False),
    ]


@pytest.mark.parametrize("cmd", ["nach Größe sortieren", "sort by size"])
def test_size_recognised(cmd: str) -> None:
    plan = try_quick_plan(cmd, _sized_files(), TARGET)
    assert plan is not None
    folders = {a.destination.name for a in plan.actions if a.op_type == OpType.create_folder}
    assert folders == {"Klein (unter 1 MB)", "Mittel (1-100 MB)", "Groß (über 100 MB)"}


# ---------------------------------------------------------------------------
# Alphabetical planner
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", ["alphabetisch ordnen", "sort by name", "sortiere nach Namen"])
def test_alphabetical_recognised(cmd: str) -> None:
    plan = try_quick_plan(cmd, FILES, TARGET)
    assert plan is not None
    folders = {a.destination.name for a in plan.actions if a.op_type == OpType.create_folder}
    # report.pdf, photo.jpg, notes.txt, data.csv, image.jpg
    assert folders == {"R", "P", "N", "D", "I"}


def test_alphabetical_digit_and_symbol_buckets() -> None:
    files = [
        FileInfo(path=TARGET / "1file.txt", name="1file.txt", extension=".txt",
                 size_bytes=10, created=datetime(2024, 1, 1), modified=datetime(2024, 1, 1),
                 is_dir=False),
        FileInfo(path=TARGET / "_hidden.txt", name="_hidden.txt", extension=".txt",
                 size_bytes=10, created=datetime(2024, 1, 1), modified=datetime(2024, 1, 1),
                 is_dir=False),
    ]
    plan = try_quick_plan("alphabetisch sortieren", files, TARGET)
    assert plan is not None
    folders = {a.destination.name for a in plan.actions if a.op_type == OpType.create_folder}
    assert folders == {"0-9", "Sonstige"}


# ---------------------------------------------------------------------------
# Plan structure
# ---------------------------------------------------------------------------

def test_creates_one_folder_per_extension() -> None:
    plan = try_quick_plan("Sortiere nach Dateiendung", FILES, TARGET)
    assert plan is not None
    folder_actions = [a for a in plan.actions if a.op_type == OpType.create_folder]
    unique_exts = {f.extension for f in FILES if not f.is_dir}
    assert len(folder_actions) == len(unique_exts)


def test_creates_move_for_every_file() -> None:
    plan = try_quick_plan("sort by extension", FILES, TARGET)
    assert plan is not None
    move_actions = [a for a in plan.actions if a.op_type == OpType.move]
    assert len(move_actions) == len(FILES)


def test_destinations_are_inside_target() -> None:
    plan = try_quick_plan("Dateiendung", FILES, TARGET)
    assert plan is not None
    for action in plan.actions:
        assert str(action.destination).startswith(str(TARGET))


def test_file_grouped_in_correct_subfolder() -> None:
    plan = try_quick_plan("sort by extension", FILES, TARGET)
    assert plan is not None
    for action in plan.actions:
        if action.op_type != OpType.move:
            continue
        assert action.source is not None
        ext = action.source.suffix.lower()
        expected_folder = _ext_to_folder_name(ext)
        assert expected_folder in str(action.destination)


def test_create_folder_before_move() -> None:
    """All create_folder actions must appear before any move action."""
    plan = try_quick_plan("Dateiendung", FILES, TARGET)
    assert plan is not None
    ops = [a.op_type for a in plan.actions]
    last_create = max((i for i, o in enumerate(ops) if o == OpType.create_folder), default=-1)
    first_move  = min((i for i, o in enumerate(ops) if o == OpType.move),          default=len(ops))
    assert last_create < first_move, "create_folder must precede all move actions"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_file_list_returns_plan_with_no_actions() -> None:
    plan = try_quick_plan("sort by extension", [], TARGET)
    assert plan is not None
    assert plan.actions == []


def test_directories_are_excluded() -> None:
    mixed = FILES + [_make_dir("subdir", TARGET)]
    plan = try_quick_plan("sort by extension", mixed, TARGET)
    assert plan is not None
    move_actions = [a for a in plan.actions if a.op_type == OpType.move]
    # No directory should appear as a source
    assert all(not any(a.source == (TARGET / "subdir") for a in move_actions)
               for _ in [None])


def test_no_extension_files_go_to_sonstige() -> None:
    files = [
        FileInfo(
            path=TARGET / "Makefile",
            name="Makefile",
            extension="",
            size_bytes=512,
            created=datetime(2024, 1, 1),
            modified=datetime(2024, 1, 1),
            is_dir=False,
        )
    ]
    plan = try_quick_plan("sort by extension", files, TARGET)
    assert plan is not None
    move = next(a for a in plan.actions if a.op_type == OpType.move)
    assert "Sonstige" in str(move.destination)


def test_ext_to_folder_name() -> None:
    assert _ext_to_folder_name(".pdf") == "PDF"
    assert _ext_to_folder_name(".jpeg") == "JPEG"
    assert _ext_to_folder_name("") == "Sonstige"
    assert _ext_to_folder_name(".TXT") == "TXT"
