"""Test is_safe_destination: paths outside the root must be rejected."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.mover import is_safe_destination


def test_file_inside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert is_safe_destination(root / "sub" / "file.txt", root)


def test_file_at_root_level(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert is_safe_destination(root / "file.txt", root)


def test_root_itself_accepted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert is_safe_destination(root, root)


def test_sibling_dir_rejected(tmp_path):
    root  = tmp_path / "root"
    other = tmp_path / "other"
    root.mkdir(); other.mkdir()
    assert not is_safe_destination(other / "file.txt", root)


def test_parent_dir_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert not is_safe_destination(tmp_path / "file.txt", root)


def test_dotdot_escape_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sneaky = root / ".." / "evil" / "file.txt"
    assert not is_safe_destination(sneaky, root)


def test_dotdot_within_root_accepted(tmp_path):
    root = tmp_path / "root"
    sub  = root / "a" / "b"
    sub.mkdir(parents=True)
    within = sub / ".." / "c.txt"   # resolves to root/a/c.txt – still inside
    assert is_safe_destination(within, root)


def test_absolute_outside_path_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert not is_safe_destination(Path("/etc/passwd"), root)
