"""Central animation state machine – purely visual, zero file-system access."""
from __future__ import annotations

from enum import Enum
from typing import Any


class AnimState(Enum):
    IDLE      = "idle"
    SCANNING  = "scanning"
    THINKING  = "thinking"
    EXECUTING = "executing"
    SUCCESS   = "success"
    ERROR     = "error"


class AnimationEngine:
    """
    Broadcasts state changes to all registered HUD widgets.

    Safety contract:
    - set_state() is always called from the main thread (via after()).
    - Crashes in individual widgets are swallowed; the engine keeps running.
    - No file-system operations here, ever.
    """

    def __init__(self, cfg: dict) -> None:
        ui = cfg.get("ui", {})
        self._enabled  = bool(ui.get("animations_enabled", True))
        self._reduced  = bool(ui.get("reduced_motion", False))
        self._boot_seq = bool(ui.get("boot_sequence", True))
        self._state    = AnimState.IDLE
        self._widgets: list[Any] = []
        self._event_cbs: list[Any] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def reduced_motion(self) -> bool:
        return self._reduced

    @property
    def boot_sequence(self) -> bool:
        return self._boot_seq

    @property
    def state(self) -> AnimState:
        return self._state

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, widget: Any) -> None:
        self._widgets.append(widget)

    def subscribe_events(self, callback: Any) -> None:
        self._event_cbs.append(callback)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def set_state(self, state: AnimState) -> None:
        self._state = state
        for w in self._widgets:
            try:
                w.on_state_change(state)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Event bus (purely informational – no file ops)
    # ------------------------------------------------------------------

    def emit_event(self, event_type: str, data: Any = None) -> None:
        for cb in self._event_cbs:
            try:
                cb(event_type, data)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Settings hot-reload
    # ------------------------------------------------------------------

    def update_settings(self, cfg: dict) -> None:
        ui = cfg.get("ui", {})
        self._enabled  = bool(ui.get("animations_enabled", True))
        self._reduced  = bool(ui.get("reduced_motion", False))
        self._boot_seq = bool(ui.get("boot_sequence", True))
