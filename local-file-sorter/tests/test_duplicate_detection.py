"""Tests for duplicate detection during move_file()."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.mover import is_duplicate, move_file


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    return tmp_path


def test_is_duplicate_identical_content(workdir: Path) -> None:
    a = workdir / "a.txt"
    b = workdir / "b.txt"
    a.write_text("hello world")
    b.write_text("hello world")
    assert is_duplicate(a, b) is True


def test_is_duplicate_different_content_same_size(workdir: Path) -> None:
    a = workdir / "a.txt"
    b = workdir / "b.txt"
    a.write_text("aaaaaaaaaa")
    b.write_text("bbbbbbbbbb")
    assert is_duplicate(a, b) is False


def test_is_duplicate_different_size(workdir: Path) -> None:
    a = workdir / "a.txt"
    b = workdir / "b.txt"
    a.write_text("short")
    b.write_text("a much longer piece of text")
    assert is_duplicate(a, b) is False


def test_is_duplicate_missing_file_returns_false(workdir: Path) -> None:
    a = workdir / "a.txt"
    a.write_text("hi")
    assert is_duplicate(a, workdir / "missing.txt") is False


def test_move_file_duplicate_goes_to_duplicate_folder(workdir: Path) -> None:
    src_dir = workdir / "src"
    dst_dir = workdir / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    existing = dst_dir / "report.pdf"
    existing.write_text("same content")

    incoming = src_dir / "report.pdf"
    incoming.write_text("same content")

    result = move_file(incoming, existing)

    assert result.success is True
    assert result.is_duplicate is True
    assert result.destination_final.parent.name == "_Duplikate"
    assert result.destination_final.exists()
    assert not incoming.exists()
    # Original file at destination must be untouched
    assert existing.read_text() == "same content"


def test_move_file_conflict_but_not_duplicate_gets_renamed(workdir: Path) -> None:
    src_dir = workdir / "src"
    dst_dir = workdir / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    existing = dst_dir / "report.pdf"
    existing.write_text("original content")

    incoming = src_dir / "report.pdf"
    incoming.write_text("different content")

    result = move_file(incoming, existing)

    assert result.success is True
    assert result.is_duplicate is False
    assert result.destination_final.name == "report_1.pdf"
    assert result.destination_final.parent == dst_dir
    assert existing.read_text() == "original content"
    assert result.destination_final.read_text() == "different content"


def test_move_file_no_conflict_is_not_duplicate(workdir: Path) -> None:
    src_dir = workdir / "src"
    dst_dir = workdir / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    incoming = src_dir / "new.txt"
    incoming.write_text("data")

    result = move_file(incoming, dst_dir / "new.txt")

    assert result.success is True
    assert result.is_duplicate is False
    assert result.destination_final == dst_dir / "new.txt"


def test_second_duplicate_gets_renamed_inside_duplicate_folder(workdir: Path) -> None:
    src_dir = workdir / "src"
    dst_dir = workdir / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    existing = dst_dir / "report.pdf"
    existing.write_text("same content")

    first = src_dir / "report_copy1.pdf"
    first.write_text("same content")
    second = src_dir / "report_copy2.pdf"
    second.write_text("same content")

    r1 = move_file(first, existing)
    r2 = move_file(second, existing)

    assert r1.destination_final != r2.destination_final
    assert r1.destination_final.parent.name == "_Duplikate"
    assert r2.destination_final.parent.name == "_Duplikate"
