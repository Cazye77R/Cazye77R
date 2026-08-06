"""Gesture recognition from MediaPipe hand landmarks.

``GestureDetector`` is a small state machine driven one frame at a time by
:meth:`GestureDetector.update`. It owns *all* edge detection (click, double
click, drag, right click) so that every entry point — the OpenCV app and the
Streamlit UI — behaves identically; callers only dispatch, they never derive
edges themselves.

Settings resolution: values are read from an optional ``settings`` mapping and
fall back to :mod:`config` *dynamically* on every access, so changing a slider
at runtime takes effect on the next frame without rebuilding the detector.
"""

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

# A scroll gesture must move at least this far (normalized units) between two
# frames before it counts as directional, so a resting hand does not scroll.
_SCROLL_DEADZONE = 0.004


class GestureDetector:
    def __init__(self, landmarks=None, settings=None):
        self._lm = landmarks
        self._settings = settings
        # drag state
        self._pinch_start_time: float | None = None
        self._is_drag_active: bool = False
        self._drag_just_started: bool = False
        self._drag_just_ended: bool = False
        self._click_just_fired: bool = False
        # double-click state
        self._first_click_time: float | None = None
        self._pending_action: str | None = None
        # right-click edge state
        self._prev_right_click: bool = False
        self._right_click_just_fired: bool = False
        # scroll state
        self._scroll_prev_y: float | None = None
        self._scroll_delta: float = 0.0

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_settings(self, settings) -> None:
        """Swap the settings mapping consulted on every subsequent access."""
        self._settings = settings

    def _setting(self, key: str):
        if self._settings is not None:
            value = self._settings.get(key)
            if value is not None:
                return value
        # Dynamic lookup so runtime changes to config are picked up immediately.
        return getattr(config, config.SETTING_ATTRS[key])

    # ------------------------------------------------------------------
    # Frame update — call once per frame, with None when no hand is visible
    # ------------------------------------------------------------------

    def update(self, landmarks=None) -> None:
        """Advance the state machine by one frame.

        Pass ``None`` when no hand is detected. That is not a no-op: it
        releases an in-progress drag (otherwise the mouse button would stay
        held down forever) and lets a queued click settle normally.
        """
        self._lm = landmarks
        now = time.time()
        has_hand = landmarks is not None
        pinching = has_hand and self.is_left_click()

        self._drag_just_started = False
        self._drag_just_ended = False
        self._click_just_fired = False
        self._right_click_just_fired = False

        # ── Left pinch: click / double click / drag ──────────────────────
        if pinching:
            if self._pinch_start_time is None:
                self._pinch_start_time = now
            elif not self._is_drag_active:
                if now - self._pinch_start_time >= self._setting("drag_threshold"):
                    self._is_drag_active = True
                    self._drag_just_started = True
                    # Starting a drag cancels any click waiting on the
                    # double-click window; it was the drag's own press.
                    self._first_click_time = None
        else:
            if self._is_drag_active:
                self._is_drag_active = False
                self._drag_just_ended = True
            elif self._pinch_start_time is not None:
                self._click_just_fired = True
                if (self._first_click_time is not None
                        and now - self._first_click_time <= self._setting("double_click_window")):
                    self._pending_action = "double_click"
                    self._first_click_time = None
                else:
                    self._first_click_time = now
            self._pinch_start_time = None

        # ── Right pinch: edge-detected, suppressed during a drag ─────────
        right = has_hand and not self._is_drag_active and self.is_right_click()
        self._right_click_just_fired = right and not self._prev_right_click
        self._prev_right_click = right

        # ── Scroll delta ─────────────────────────────────────────────────
        if has_hand and self.is_scroll_mode():
            y = self._lm[8].y
            self._scroll_delta = 0.0 if self._scroll_prev_y is None else y - self._scroll_prev_y
            self._scroll_prev_y = y
        else:
            self._scroll_prev_y = None
            self._scroll_delta = 0.0

    # ------------------------------------------------------------------
    # Click action — returns "click", "double_click", or None each frame
    # ------------------------------------------------------------------

    def get_click_action(self) -> str | None:
        """Poll for a pending click. Call this once per frame, unconditionally.

        Skipping frames (e.g. only polling while a hand is visible) would leave
        a queued click armed indefinitely and fire it much later at whatever
        the cursor happens to point at then.
        """
        if self._pending_action is not None:
            action = self._pending_action
            self._pending_action = None
            return action
        if self._first_click_time is not None:
            if time.time() - self._first_click_time > self._setting("double_click_window"):
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

    def right_click_just_fired(self) -> bool:
        """True on the single frame the right-pinch closes (rising edge)."""
        return self._right_click_just_fired

    # ------------------------------------------------------------------
    # Stateless gesture queries (work on current _lm)
    # ------------------------------------------------------------------

    def cursor_position(self) -> tuple[float, float]:
        return self._lm[8].x, self._lm[8].y

    def is_left_click(self) -> bool:
        return self._pinch_distance(4, 8) < self._setting("pinch_threshold")

    def is_right_click(self) -> bool:
        return self._pinch_distance(4, 12) < self._setting("pinch_threshold")

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

    def scroll_delta(self) -> float:
        """Frame-to-frame y delta while in scroll mode (0.0 otherwise)."""
        return self._scroll_delta

    def is_scroll_up(self) -> bool:
        return self._scroll_delta < -_SCROLL_DEADZONE

    def is_scroll_down(self) -> bool:
        return self._scroll_delta > _SCROLL_DEADZONE

    # ------------------------------------------------------------------

    def _is_extended(self, finger: str) -> bool:
        tip_idx, pip_idx = _FINGER_TIPS[finger]
        return self._lm[tip_idx].y < self._lm[pip_idx].y

    def _pinch_distance(self, a: int, b: int) -> float:
        pa = np.array([self._lm[a].x, self._lm[a].y])
        pb = np.array([self._lm[b].x, self._lm[b].y])
        return float(np.linalg.norm(pa - pb))
