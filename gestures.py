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
    def __init__(self, landmarks):
        self._lm = landmarks

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
