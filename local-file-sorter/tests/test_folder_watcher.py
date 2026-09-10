"""Tests for FolderWatcher – polling-based new-file detection."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.watcher import FolderWatcher

_POLL = 0.05  # fast interval for tests


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture()
def folder(tmp_path: Path) -> Path:
    return tmp_path


def test_detects_new_file(folder: Path) -> None:
    (folder / "existing.txt").write_text("x")
    detected: list[list[Path]] = []
    watcher = FolderWatcher(folder, on_new_files=detected.append, poll_interval=_POLL)
    watcher.start()
    try:
        (folder / "new.txt").write_text("y")
        assert _wait_for(lambda: len(detected) > 0)
        assert folder / "new.txt" in detected[0]
        assert folder / "existing.txt" not in detected[0]
    finally:
        watcher.stop()


def test_no_callback_when_nothing_changes(folder: Path) -> None:
    (folder / "a.txt").write_text("x")
    detected: list[list[Path]] = []
    watcher = FolderWatcher(folder, on_new_files=detected.append, poll_interval=_POLL)
    watcher.start()
    try:
        time.sleep(_POLL * 6)
        assert detected == []
    finally:
        watcher.stop()


def test_stop_halts_detection(folder: Path) -> None:
    detected: list[list[Path]] = []
    watcher = FolderWatcher(folder, on_new_files=detected.append, poll_interval=_POLL)
    watcher.start()
    watcher.stop()
    assert watcher.is_running is False
    (folder / "after_stop.txt").write_text("z")
    time.sleep(_POLL * 6)
    assert detected == []


def test_already_processed_files_not_reported_again(folder: Path) -> None:
    detected: list[list[Path]] = []
    watcher = FolderWatcher(folder, on_new_files=detected.append, poll_interval=_POLL)
    watcher.start()
    try:
        (folder / "one.txt").write_text("a")
        assert _wait_for(lambda: len(detected) >= 1)
        detected.clear()
        time.sleep(_POLL * 6)
        assert detected == []
    finally:
        watcher.stop()


def test_is_running_reflects_state(folder: Path) -> None:
    watcher = FolderWatcher(folder, on_new_files=lambda _: None, poll_interval=_POLL)
    assert watcher.is_running is False
    watcher.start()
    assert watcher.is_running is True
    watcher.stop()
    assert watcher.is_running is False


def test_missing_folder_does_not_crash(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    detected: list[list[Path]] = []
    watcher = FolderWatcher(missing, on_new_files=detected.append, poll_interval=_POLL)
    watcher.start()
    try:
        time.sleep(_POLL * 4)
        assert detected == []
    finally:
        watcher.stop()
