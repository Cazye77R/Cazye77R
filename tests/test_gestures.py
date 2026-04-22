import sys
import os
import pytest
from unittest.mock import MagicMock, patch

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


def _pinch_lm(close: bool):
    offset = config.PINCH_THRESHOLD * (0.4 if close else 2.0)
    return _make_landmarks({4: (0.5, 0.5), 8: (0.5 + offset, 0.5)})


class TestDragState:
    def test_no_drag_initially(self):
        d = GestureDetector()
        assert d.is_dragging() is False
        assert d.drag_just_started() is False
        assert d.drag_just_ended() is False

    def test_drag_starts_after_threshold(self):
        d = GestureDetector()
        lm = _pinch_lm(close=True)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(lm)
            assert d.is_dragging() is False

            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(lm)
            assert d.is_dragging() is True
            assert d.drag_just_started() is True

    def test_drag_just_started_is_one_frame_only(self):
        d = GestureDetector()
        lm = _pinch_lm(close=True)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(lm)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(lm)
            assert d.drag_just_started() is True
            d.update(lm)                          # third frame, still pinching
            assert d.drag_just_started() is False
            assert d.is_dragging() is True

    def test_drag_ends_on_pinch_release(self):
        d = GestureDetector()
        pinch = _pinch_lm(close=True)
        release = _pinch_lm(close=False)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(pinch)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(pinch)
            assert d.is_dragging() is True

            d.update(release)
            assert d.is_dragging() is False
            assert d.drag_just_ended() is True

    def test_drag_just_ended_is_one_frame_only(self):
        d = GestureDetector()
        pinch = _pinch_lm(close=True)
        release = _pinch_lm(close=False)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(pinch)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(pinch)
            d.update(release)
            assert d.drag_just_ended() is True
            d.update(release)
            assert d.drag_just_ended() is False

    def test_no_drag_on_quick_release(self):
        d = GestureDetector()
        pinch = _pinch_lm(close=True)
        release = _pinch_lm(close=False)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(pinch)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC * 0.5
            d.update(release)
            assert d.is_dragging() is False
            assert d.drag_just_ended() is False

    def test_click_fires_on_quick_release(self):
        d = GestureDetector()
        pinch = _pinch_lm(close=True)
        release = _pinch_lm(close=False)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(pinch)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC * 0.5
            d.update(release)
            assert d.click_just_fired() is True

    def test_click_does_not_fire_after_drag(self):
        d = GestureDetector()
        pinch = _pinch_lm(close=True)
        release = _pinch_lm(close=False)
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            mock_time.time.return_value = t0
            d.update(pinch)
            mock_time.time.return_value = t0 + config.DRAG_THRESHOLD_SEC + 0.01
            d.update(pinch)
            d.update(release)
            assert d.click_just_fired() is False


def _quick_click(detector, t_start, mock_time):
    """Simulate one quick pinch-release at t_start (same timestamp, no drag)."""
    mock_time.time.return_value = t_start
    detector.update(_pinch_lm(close=True))
    detector.update(_pinch_lm(close=False))


class TestGetClickAction:
    def test_returns_none_before_any_gesture(self):
        assert GestureDetector().get_click_action() is None

    def test_returns_none_while_waiting_for_second_click(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            # still within window
            mock_time.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW * 0.5
            assert d.get_click_action() is None

    def test_returns_click_after_window_expires(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            mock_time.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW + 0.01
            assert d.get_click_action() == "click"

    def test_returns_none_after_click_consumed(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            mock_time.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW + 0.01
            d.get_click_action()
            assert d.get_click_action() is None

    def test_returns_double_click_on_second_click_within_window(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            t1 = t0 + config.DOUBLE_CLICK_WINDOW * 0.6
            _quick_click(d, t1, mock_time)
            assert d.get_click_action() == "double_click"

    def test_double_click_consumed_only_once(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            t1 = t0 + config.DOUBLE_CLICK_WINDOW * 0.6
            _quick_click(d, t1, mock_time)
            d.get_click_action()
            assert d.get_click_action() is None

    def test_second_click_after_window_starts_new_sequence(self):
        d = GestureDetector()
        t0 = 1000.0
        with patch("gestures.time") as mock_time:
            _quick_click(d, t0, mock_time)
            # consume the first click (window expired)
            mock_time.time.return_value = t0 + config.DOUBLE_CLICK_WINDOW + 0.01
            assert d.get_click_action() == "click"
            # second click starts a fresh sequence
            t1 = t0 + config.DOUBLE_CLICK_WINDOW + 0.05
            _quick_click(d, t1, mock_time)
            mock_time.time.return_value = t1 + config.DOUBLE_CLICK_WINDOW * 0.5
            assert d.get_click_action() is None  # still waiting
