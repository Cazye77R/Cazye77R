"""Tests for elephant.memory.decay (decay_memories, touch_memory)."""

import math
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest

from elephant.memory.markdown_store import save_memory
from elephant.memory.decay import decay_memories, _MIN_IMPORTANCE
from elephant.memory.markdown_store import touch_memory


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_memories(tmp_path, monkeypatch):
    """Redirect settings.memory_path to a temp directory."""
    for cat in ("general", "projects", "conversations"):
        (tmp_path / cat).mkdir()

    import elephant.config as cfg
    import elephant.memory.markdown_store as store
    import elephant.memory.decay as decay_mod

    monkeypatch.setattr(cfg.settings, "memory_path", tmp_path)
    monkeypatch.setattr(store.settings, "memory_path", tmp_path)
    monkeypatch.setattr(decay_mod.settings, "memory_path", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# decay_memories — old memory (> 1 day) gets its importance reduced
# ---------------------------------------------------------------------------

def test_decay_reduces_importance_for_old_memory(tmp_memories):
    path = save_memory("general", "Old Memory", "content", [], importance=0.8)

    # Fake "now" to be 10 days after the memory was last accessed
    future = datetime.utcnow() + timedelta(days=10)
    with patch("elephant.memory.decay._utcnow", return_value=future):
        report = decay_memories(decay_rate=0.1)

    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert post["importance"] < 0.8
    assert report["decayed"] == 1


# ---------------------------------------------------------------------------
# decay_memories — recent memory (< 1 day) is skipped
# ---------------------------------------------------------------------------

def test_decay_skips_recent_memory(tmp_memories):
    save_memory("general", "New Memory", "content", [], importance=0.8)

    # No time travel — memory was just saved (0 days old)
    report = decay_memories(decay_rate=0.1)

    assert report["decayed"] == 0
    assert report["skipped"] == 1


# ---------------------------------------------------------------------------
# Importance never goes below _MIN_IMPORTANCE
# ---------------------------------------------------------------------------

def test_importance_floor_respected(tmp_memories):
    path = save_memory("general", "Very Old", "content", [], importance=0.06)

    far_future = datetime.utcnow() + timedelta(days=10000)
    with patch("elephant.memory.decay._utcnow", return_value=far_future):
        decay_memories(decay_rate=0.5)

    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert post["importance"] >= _MIN_IMPORTANCE


# ---------------------------------------------------------------------------
# dry_run=True — report shows change but file is not modified
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write_file(tmp_memories):
    path = save_memory("general", "Dry Run", "content", [], importance=0.9)
    original_text = path.read_text(encoding="utf-8")

    future = datetime.utcnow() + timedelta(days=30)
    with patch("elephant.memory.decay._utcnow", return_value=future):
        report = decay_memories(decay_rate=0.1, dry_run=True)

    assert path.read_text(encoding="utf-8") == original_text
    assert report["decayed"] == 1  # counted but not written


# ---------------------------------------------------------------------------
# touch_memory updates last_accessed without changing updated_at
# ---------------------------------------------------------------------------

def test_touch_memory_updates_last_accessed(tmp_memories):
    path = save_memory("general", "Touch Test", "content", [])
    post_before = frontmatter.loads(path.read_text(encoding="utf-8"))
    updated_at_before = post_before["updated_at"]

    touch_memory(path)

    post_after = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert "last_accessed" in post_after
    assert post_after["updated_at"] == updated_at_before  # unchanged


# ---------------------------------------------------------------------------
# Report structure has correct keys and types
# ---------------------------------------------------------------------------

def test_report_structure(tmp_memories):
    save_memory("general", "A", "a", [])
    future = datetime.utcnow() + timedelta(days=5)
    with patch("elephant.memory.decay._utcnow", return_value=future):
        report = decay_memories()

    assert set(report.keys()) == {"checked", "decayed", "skipped", "updated_files"}
    assert isinstance(report["checked"], int)
    assert isinstance(report["decayed"], int)
    assert isinstance(report["skipped"], int)
    assert isinstance(report["updated_files"], list)


# ---------------------------------------------------------------------------
# Custom decay_rate is respected
# ---------------------------------------------------------------------------

def test_custom_decay_rate(tmp_memories):
    path = save_memory("general", "Rate Test", "content", [], importance=0.8)
    days = 5
    rate = 0.2
    future = datetime.utcnow() + timedelta(days=days)

    with patch("elephant.memory.decay._utcnow", return_value=future):
        decay_memories(decay_rate=rate)

    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    expected = round(max(_MIN_IMPORTANCE, 0.8 * math.exp(-rate * days)), 4)
    assert abs(post["importance"] - expected) < 0.001


# ---------------------------------------------------------------------------
# Zero / very-low importance does not go negative
# ---------------------------------------------------------------------------

def test_zero_importance_stays_at_floor(tmp_memories):
    path = save_memory("general", "Zero", "content", [], importance=0.0)
    # Pydantic clamps to 0 due to ge=0.0, but we test the decay output
    # Manually write importance=0.0 past pydantic
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    post["importance"] = 0.0
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    far_future = datetime.utcnow() + timedelta(days=1000)
    with patch("elephant.memory.decay._utcnow", return_value=far_future):
        decay_memories(decay_rate=1.0)

    post_after = frontmatter.loads(path.read_text(encoding="utf-8"))
    # Either stays at 0.0 (diff < 0.001 so skipped) or is floored at _MIN_IMPORTANCE
    assert post_after["importance"] >= 0.0
