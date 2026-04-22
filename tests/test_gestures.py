import sys
import os
import pytest
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


def _scroll_landmarks(index_up: bool, middle_up: bool, ring_up: bool, pinky_up: bool):
    """
    Build landmarks where fingers are extended (tip.y < PIP.y) or folded.
    Pairs: index(8,6), middle(12,10), ring(16,14), pinky(20,18).
    """
    def _ys(extended):
        return (0.3, 0.5) if extended else (0.7, 0.5)  # (tip_y, PIP_y)

    tip8, pip6 = _ys(index_up)
    tip12, pip10 = _ys(middle_up)
    tip16, pip14 = _ys(ring_up)
    tip20, pip18 = _ys(pinky_up)
    return _make_landmarks({
        8: (0.5, tip8), 6: (0.5, pip6),
        12: (0.5, tip12), 10: (0.5, pip10),
        16: (0.5, tip16), 14: (0.5, pip14),
        20: (0.5, tip20), 18: (0.5, pip18),
    })


class TestIsScrollMode:
    def test_true_when_index_and_middle_extended_others_folded(self):
        lm = _scroll_landmarks(index_up=True, middle_up=True, ring_up=False, pinky_up=False)
        assert GestureDetector(lm).is_scroll_mode() is True

    def test_false_when_only_index_extended(self):
        lm = _scroll_landmarks(index_up=True, middle_up=False, ring_up=False, pinky_up=False)
        assert GestureDetector(lm).is_scroll_mode() is False

    def test_false_when_all_fingers_extended(self):
        lm = _scroll_landmarks(index_up=True, middle_up=True, ring_up=True, pinky_up=True)
        assert GestureDetector(lm).is_scroll_mode() is False

    def test_false_when_ring_also_extended(self):
        lm = _scroll_landmarks(index_up=True, middle_up=True, ring_up=True, pinky_up=False)
        assert GestureDetector(lm).is_scroll_mode() is False


class TestGetScrollDelta:
    def test_positive_delta_when_hand_moved_down(self):
        lm = _make_landmarks({8: (0.5, 0.6)})
        assert GestureDetector(lm).get_scroll_delta(0.4) == pytest.approx(0.2)

    def test_negative_delta_when_hand_moved_up(self):
        lm = _make_landmarks({8: (0.5, 0.3)})
        assert GestureDetector(lm).get_scroll_delta(0.5) == pytest.approx(-0.2)

    def test_zero_delta_when_hand_did_not_move(self):
        lm = _make_landmarks({8: (0.5, 0.5)})
        assert GestureDetector(lm).get_scroll_delta(0.5) == pytest.approx(0.0)
