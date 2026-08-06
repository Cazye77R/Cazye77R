"""Tests for the edge detection and dispatch behaviour fixed in gestures.py.

Covers the three defects that were user-visible:
  * right click auto-repeated while the gesture was held
  * a queued single click was never delivered once the hand left the frame
  * a drag never ended if the hand vanished mid-drag (mouse stayed held down)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from gestures import GestureDetector  # noqa: E402

FAR = 0.5  # comfortably beyond any pinch threshold


def _lm(pos=None):
    """21 landmarks; every index defaults to (0.5, 0.5)."""
    pos = pos or {}
    points = []
    for i in range(21):
        p = MagicMock()
        p.x, p.y = pos.get(i, (0.5, 0.5))
        points.append(p)
    return points


def _left_pinch(closed: bool):
    """Thumb+index pinched (or not); middle held far away."""
    gap = config.PINCH_THRESHOLD * (0.4 if closed else 2.0)
    return _lm({4: (0.5, 0.5), 8: (0.5 + gap, 0.5), 12: (0.5 + FAR, 0.5)})


def _right_pinch(closed: bool):
    """Thumb+middle pinched (or not); index held far away."""
    gap = config.PINCH_THRESHOLD * (0.4 if closed else 2.0)
    return _lm({4: (0.5, 0.5), 12: (0.5 + gap, 0.5), 8: (0.5 + FAR, 0.5)})


def _scroll(index_y: float):
    """Index+middle extended, ring+pinky folded, index tip at index_y."""
    return _lm({
        8: (0.5, index_y), 6: (0.5, index_y + 0.2),
        12: (0.5, 0.3), 10: (0.5, 0.5),
        16: (0.5, 0.7), 14: (0.5, 0.5),
        20: (0.5, 0.7), 18: (0.5, 0.5),
        4: (0.5, 0.9),
    })


# ── Right-click edge detection ────────────────────────────────────────────

class TestRightClickEdge:
    def test_fires_once_on_close(self):
        d = GestureDetector()
        d.update(_right_pinch(True))
        assert d.right_click_just_fired() is True

    def test_does_not_repeat_while_held(self):
        d = GestureDetector()
        held = _right_pinch(True)
        d.update(held)
        fires = 0
        for _ in range(100):
            d.update(held)
            fires += d.right_click_just_fired()
        assert fires == 0, "Rechtsklick darf beim Halten nicht wiederholt feuern"

    def test_fires_again_after_release_and_repinch(self):
        d = GestureDetector()
        total = 0
        for _ in range(2):
            d.update(_right_pinch(True))
            total += d.right_click_just_fired()
            d.update(_right_pinch(False))
        assert total == 2

    def test_not_fired_without_hand(self):
        d = GestureDetector()
        d.update(None)
        assert d.right_click_just_fired() is False

    def test_suppressed_during_drag(self):
        d = GestureDetector()
        # Thumb close to BOTH index and middle: a drag plus a right pinch.
        both = _lm({4: (0.5, 0.5),
                      8: (0.5 + config.PINCH_THRESHOLD * 0.3, 0.5),
                      12: (0.5 + config.PINCH_THRESHOLD * 0.3, 0.5)})
        t0 = 1000.0
        with patch("gestures.time") as clock:
            clock.time.return_value = t0
            d.update(both)
            clock.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(both)
            assert d.is_dragging() is True
            assert d.right_click_just_fired() is False


# ── Click delivery ────────────────────────────────────────────────────────

class TestClickDelivery:
    def test_click_is_delivered_after_hand_leaves_frame(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as clock:
            clock.time.return_value = t0
            d.update(_left_pinch(True))
            d.update(_left_pinch(False))       # quick release -> click queued
            assert d.get_click_action() is None

            # Hand gone. Polling must continue and the click must still land.
            clock.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW + 0.01
            d.update(None)
            assert d.get_click_action() == "click"

    def test_click_does_not_fire_late_after_being_delivered(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as clock:
            clock.time.return_value = t0
            d.update(_left_pinch(True))
            d.update(_left_pinch(False))
            clock.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW + 0.01
            assert d.get_click_action() == "click"
            clock.time.return_value = t0 + 60.0
            for _ in range(10):
                d.update(None)
                assert d.get_click_action() is None

    def test_starting_a_drag_cancels_a_queued_click(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as clock:
            clock.time.return_value = t0
            d.update(_left_pinch(True))
            d.update(_left_pinch(False))       # click queued
            clock.time.return_value = t0 + 0.05
            d.update(_left_pinch(True))        # press again...
            clock.time.return_value = t0 + 0.05 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(_left_pinch(True))        # ...and hold into a drag
            assert d.is_dragging() is True
            # No stray click may be waiting behind the drag.
            clock.time.return_value = t0 + 60.0
            assert d.get_click_action() is None


# ── Drag safety ───────────────────────────────────────────────────────────

class TestDragRelease:
    def test_drag_ends_when_hand_disappears(self):
        d = GestureDetector()
        held = _left_pinch(True)
        t0 = 1000.0
        with patch("gestures.time") as clock:
            clock.time.return_value = t0
            d.update(held)
            clock.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(held)
            assert d.is_dragging() is True

            d.update(None)   # hand leaves the frame
            assert d.is_dragging() is False
            assert d.drag_just_ended() is True, \
                "sonst bleibt die Maustaste dauerhaft gedrueckt"


# ── Scroll direction ──────────────────────────────────────────────────────

class TestScrollDirection:
    def test_no_direction_on_first_scroll_frame(self):
        d = GestureDetector()
        d.update(_scroll(0.5))
        assert d.is_scroll_up() is False
        assert d.is_scroll_down() is False

    def test_hand_moving_up_scrolls_up(self):
        d = GestureDetector()
        d.update(_scroll(0.5))
        d.update(_scroll(0.4))          # smaller y = higher on screen
        assert d.is_scroll_up() is True
        assert d.is_scroll_down() is False

    def test_hand_moving_down_scrolls_down(self):
        d = GestureDetector()
        d.update(_scroll(0.4))
        d.update(_scroll(0.5))
        assert d.is_scroll_down() is True
        assert d.is_scroll_up() is False

    def test_tiny_jitter_is_inside_the_deadzone(self):
        d = GestureDetector()
        d.update(_scroll(0.5))
        d.update(_scroll(0.5005))
        assert d.is_scroll_up() is False
        assert d.is_scroll_down() is False

    def test_leaving_scroll_mode_clears_direction(self):
        d = GestureDetector()
        d.update(_scroll(0.5))
        d.update(_scroll(0.4))
        assert d.is_scroll_up() is True
        d.update(None)
        assert d.is_scroll_up() is False


# ── Settings injection ────────────────────────────────────────────────────

class TestSettingsInjection:
    def test_injected_threshold_overrides_config(self):
        gap = config.PINCH_THRESHOLD * 2.0
        lm = _lm({4: (0.5, 0.5), 8: (0.5 + gap, 0.5)})
        assert GestureDetector(lm).is_left_click() is False
        loose = GestureDetector(lm, settings={"pinch_threshold": gap * 2})
        assert loose.is_left_click() is True

    def test_falls_back_to_config_for_absent_keys(self):
        lm = _left_pinch(True)
        d = GestureDetector(lm, settings={"smooth_factor": 0.9})
        assert d.is_left_click() is True   # pinch_threshold came from config

    def test_set_settings_takes_effect_immediately(self):
        gap = config.PINCH_THRESHOLD * 2.0
        lm = _lm({4: (0.5, 0.5), 8: (0.5 + gap, 0.5)})
        d = GestureDetector(lm)
        assert d.is_left_click() is False
        d.set_settings({"pinch_threshold": gap * 2})
        assert d.is_left_click() is True
