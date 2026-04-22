import numpy as np
import config


class GestureDetector:
    def __init__(self, landmarks):
        self._lm = landmarks

    def cursor_position(self) -> tuple[float, float]:
        return self._lm[8].x, self._lm[8].y

    def is_left_click(self) -> bool:
        return self._pinch_distance(4, 8) < config.PINCH_THRESHOLD

    def is_right_click(self) -> bool:
        return self._pinch_distance(4, 12) < config.PINCH_THRESHOLD

    def is_scroll_up(self) -> bool:
        # TODO: implement scroll-up gesture
        return False

    def is_scroll_down(self) -> bool:
        # TODO: implement scroll-down gesture
        return False

    def _pinch_distance(self, a: int, b: int) -> float:
        pa = np.array([self._lm[a].x, self._lm[a].y])
        pb = np.array([self._lm[b].x, self._lm[b].y])
        return float(np.linalg.norm(pa - pb))
