"""Test automatic conflict-resolution suffix logic (_1, _2, …)."""
from __future__ import annotations

import pytest

from src.core.mover import move_file, resolve_conflict


# ---------------------------------------------------------------------------
# resolve_conflict
# ---------------------------------------------------------------------------

def test_no_conflict_unchanged(tmp_path):
    dest = tmp_path / "file.txt"
    assert resolve_conflict(dest) == dest


def test_first_conflict_gets_suffix_1(tmp_path):
    dest = tmp_path / "file.txt"
    dest.touch()
    assert resolve_conflict(dest) == tmp_path / "file_1.txt"


def test_two_conflicts_get_suffix_2(tmp_path):
    dest = tmp_path / "file.txt"
    dest.touch()
    (tmp_path / "file_1.txt").touch()
    assert resolve_conflict(dest) == tmp_path / "file_2.txt"


def test_no_extension_supported(tmp_path):
    dest = tmp_path / "Makefile"
    dest.touch()
    assert resolve_conflict(dest) == tmp_path / "Makefile_1"


def test_multiple_dots_in_stem(tmp_path):
    dest = tmp_path / "archive.tar.gz"
    dest.touch()
    assert resolve_conflict(dest) == tmp_path / "archive.tar_1.gz"


# ---------------------------------------------------------------------------
# move_file conflict behaviour
# ---------------------------------------------------------------------------

def test_move_auto_renames_on_conflict(tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("hello")
    dst_dir = tmp_path / "dest"
    dst_dir.mkdir()
    existing = dst_dir / "source.txt"
    existing.write_text("original")

    result = move_file(src, existing)

    assert result.success
    assert result.destination_final == dst_dir / "source_1.txt"
    assert not src.exists()
    assert existing.exists()                        # original untouched
    assert (dst_dir / "source_1.txt").read_text() == "hello"


def test_move_creates_parent_dirs(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("data")
    deep = tmp_path / "x" / "y" / "z" / "a.txt"

    result = move_file(src, deep)

    assert result.success
    assert deep.exists()
    assert deep.read_text() == "data"


def test_move_missing_source_fails(tmp_path):
    result = move_file(tmp_path / "ghost.txt", tmp_path / "out.txt")
    assert not result.success
    assert result.error is not None
