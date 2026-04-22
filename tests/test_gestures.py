import sys
import os
import math
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gestures import GestureDetector
import config


def _make_landmarks(positions: dict[int, tuple[float, float]]) -> list:
    """Build a 21-landmark list; indices not in positions default to (0.5, 0.5)."""
    lm = []
    for i in range(21):
        point = MagicMock()
        x, y = positions.get(i, (0.5, 0.5))
        point.x = x
        point.y = y
        lm.append(point)
    return lm


class TestIsLeftClick:
    def test_returns_true_when_thumb_and_index_are_close(self):
        offset = config.PINCH_THRESHOLD * 0.5
        lm = _make_landmarks({4: (0.5, 0.5), 8: (0.5 + offset, 0.5)})
        assert GestureDetector(lm).is_left_click() is True

    def test_returns_false_when_thumb_and_index_are_far_apart(self):
        offset = config.PINCH_THRESHOLD * 2.0
        lm = _make_landmarks({4: (0.5, 0.5), 8: (0.5 + offset, 0.5)})
        assert GestureDetector(lm).is_left_click() is False

    def test_boundary_exactly_at_threshold_is_false(self):
        lm = _make_landmarks({4: (0.5, 0.5), 8: (0.5 + config.PINCH_THRESHOLD, 0.5)})
        assert GestureDetector(lm).is_left_click() is False


class TestIsRightClick:
    def test_returns_true_when_thumb_and_middle_are_close(self):
        offset = config.PINCH_THRESHOLD * 0.5
        lm = _make_landmarks({4: (0.5, 0.5), 12: (0.5 + offset, 0.5)})
        assert GestureDetector(lm).is_right_click() is True

    def test_returns_false_when_thumb_and_middle_are_far_apart(self):
        offset = config.PINCH_THRESHOLD * 2.0
        lm = _make_landmarks({4: (0.5, 0.5), 12: (0.5 + offset, 0.5)})
        assert GestureDetector(lm).is_right_click() is False


class TestCursorPosition:
    def test_returns_index_fingertip_coordinates(self):
        lm = _make_landmarks({8: (0.3, 0.7)})
        assert GestureDetector(lm).cursor_position() == (0.3, 0.7)


class TestScrollStubs:
    def test_scroll_up_returns_false(self):
        assert GestureDetector(_make_landmarks({})).is_scroll_up() is False

    def test_scroll_down_returns_false(self):
        assert GestureDetector(_make_landmarks({})).is_scroll_down() is False
