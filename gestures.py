import time
import numpy as np
import config

# Landmark indices for PIP joints and fingertips
_FINGER_TIPS = {
    "index":  (8,  6),   # (tip, PIP)
    "middle": (12, 10),
    "ring":   (16, 14),
    "pinky":  (20, 18),
}


class GestureDetector:
    def __init__(self, landmarks=None):
        self._lm = landmarks
        # drag state
        self._pinch_start_time: float | None = None
        self._is_drag_active: bool = False
        self._drag_just_started: bool = False
        self._drag_just_ended: bool = False
        self._click_just_fired: bool = False
        # double-click state
        self._first_click_time: float | None = None
        self._pending_action: str | None = None

    # ------------------------------------------------------------------
    # Frame update — call once per frame with fresh landmarks
    # ------------------------------------------------------------------

    def update(self, landmarks) -> None:
        self._lm = landmarks
        now = time.time()
        pinching = self.is_left_click()

        self._drag_just_started = False
        self._drag_just_ended = False
        self._click_just_fired = False

        if pinching:
            if self._pinch_start_time is None:
                self._pinch_start_time = now
            elif not self._is_drag_active:
                if now - self._pinch_start_time >= config.DRAG_THRESHOLD_SEC:
                    self._is_drag_active = True
                    self._drag_just_started = True
        else:
            if self._is_drag_active:
                self._is_drag_active = False
                self._drag_just_ended = True
            elif self._pinch_start_time is not None:
                self._click_just_fired = True
                if (self._first_click_time is not None
                        and now - self._first_click_time <= config.DOUBLE_CLICK_WINDOW):
                    self._pending_action = "double_click"
                    self._first_click_time = None
                else:
                    self._first_click_time = now
            self._pinch_start_time = None

    # ------------------------------------------------------------------
    # Click action — returns "click", "double_click", or None each frame
    # ------------------------------------------------------------------

    def get_click_action(self) -> str | None:
        if self._pending_action is not None:
            action = self._pending_action
            self._pending_action = None
            return action
        if self._first_click_time is not None:
            if time.time() - self._first_click_time > config.DOUBLE_CLICK_WINDOW:
                self._first_click_time = None
                return "click"
        return None

    # ------------------------------------------------------------------
    # Drag state
    # ------------------------------------------------------------------

    def is_dragging(self) -> bool:
        return self._is_drag_active

    def drag_just_started(self) -> bool:
        return self._drag_just_started

    def drag_just_ended(self) -> bool:
        return self._drag_just_ended

    def click_just_fired(self) -> bool:
        return self._click_just_fired

    # ------------------------------------------------------------------
    # Stateless gesture queries (work on current _lm)
    # ------------------------------------------------------------------

    def cursor_position(self) -> tuple[float, float]:
        return self._lm[8].x, self._lm[8].y

    def is_left_click(self) -> bool:
        return self._pinch_distance(4, 8) < config.PINCH_THRESHOLD

    def is_right_click(self) -> bool:
        return self._pinch_distance(4, 12) < config.PINCH_THRESHOLD

    def is_scroll_mode(self) -> bool:
        """Index and middle finger extended, ring and pinky folded."""
        return (
            self._is_extended("index")
            and self._is_extended("middle")
            and not self._is_extended("ring")
            and not self._is_extended("pinky")
        )

    def get_scroll_delta(self, prev_y: float) -> float:
        """Return difference in y from prev_y. Positive = down, negative = up."""
        return self._lm[8].y - prev_y

    def is_scroll_up(self) -> bool:
        # kept for backwards compatibility; use is_scroll_mode + get_scroll_delta
        return False

    def is_scroll_down(self) -> bool:
        # kept for backwards compatibility; use is_scroll_mode + get_scroll_delta
        return False

    # ------------------------------------------------------------------

    def _is_extended(self, finger: str) -> bool:
        tip_idx, pip_idx = _FINGER_TIPS[finger]
        return self._lm[tip_idx].y < self._lm[pip_idx].y

    def _pinch_distance(self, a: int, b: int) -> float:
        pa = np.array([self._lm[a].x, self._lm[a].y])
        pb = np.array([self._lm[b].x, self._lm[b].y])
        return float(np.linalg.norm(pa - pb))
