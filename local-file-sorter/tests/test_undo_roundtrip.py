"""Test move_file → log → undo_session roundtrip."""
from __future__ import annotations

import pytest

from src.core.logger import OperationLogger
from src.core.mover import move_file
from src.core.undo import undo_session


def _logged_move(src, dst, log_dir, dry_run=False):
    result = move_file(src, dst)
    logger = OperationLogger(log_dir)
    logger.log_move(result, dry_run=dry_run)
    logger.close()
    return result, logger.get_session_path()


# ---------------------------------------------------------------------------

def test_full_roundtrip(tmp_path):
    src = tmp_path / "src" / "hello.txt"
    src.parent.mkdir()
    src.write_text("hello world")
    dst = tmp_path / "dst" / "hello.txt"

    result, log_path = _logged_move(src, dst, tmp_path / "logs")

    assert result.success
    assert dst.exists()
    assert not src.exists()

    undo_results = undo_session(log_path)
    assert len(undo_results) == 1
    assert undo_results[0].success
    assert src.exists()
    assert src.read_text() == "hello world"
    assert not dst.exists()


def test_undo_conflict_skips_gracefully(tmp_path):
    src = tmp_path / "file.txt"
    src.write_text("original")
    dst = tmp_path / "dest" / "file.txt"

    result, log_path = _logged_move(src, dst, tmp_path / "logs")
    assert result.success

    src.write_text("new occupant")   # re-create src to cause conflict

    undo_results = undo_session(log_path)
    assert len(undo_results) == 1
    assert not undo_results[0].success
    assert "Konflikt" in (undo_results[0].error or "")


def test_undo_missing_destination_skips(tmp_path):
    src = tmp_path / "file.txt"
    src.write_text("data")
    dst = tmp_path / "dest" / "file.txt"

    result, log_path = _logged_move(src, dst, tmp_path / "logs")
    assert result.success
    import shutil
    shutil.move(str(dst), str(tmp_path / "moved_elsewhere.txt"))  # remove dst

    undo_results = undo_session(log_path)
    assert len(undo_results) == 1
    assert not undo_results[0].success


def test_undo_skips_dry_run_entries(tmp_path):
    """dry_run log entries must not be undone."""
    src = tmp_path / "file.txt"
    src.write_text("data")
    dst = tmp_path / "dest" / "file.txt"

    result, log_path = _logged_move(src, dst, tmp_path / "logs", dry_run=True)
    assert result.success        # the actual move DID happen in this test

    undo_results = undo_session(log_path)
    assert undo_results == [], "dry_run entries must not produce undo actions"


def test_multiple_moves_undo_in_reverse(tmp_path):
    files = []
    dsts  = []
    log_dir = tmp_path / "logs"

    logger = OperationLogger(log_dir)
    for i in range(3):
        s = tmp_path / f"file{i}.txt"
        s.write_text(f"content{i}")
        d = tmp_path / "target" / f"file{i}.txt"
        r = move_file(s, d)
        assert r.success
        logger.log_move(r)
        files.append(s)
        dsts.append(d)
    logger.close()
    log_path = logger.get_session_path()

    undo_results = undo_session(log_path)
    assert len(undo_results) == 3
    assert all(r.success for r in undo_results)
    for s in files:
        assert s.exists()
    for d in dsts:
        assert not d.exists()
