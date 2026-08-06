"""Default configuration values.

These are *defaults only*. At runtime the live values live in ``runtime.py``;
nothing should write back into this module. ``SETTING_KEYS`` is the single
source of truth for which values are tunable and profile-persistable — the
profile manager, the Streamlit UI and the gesture detector all derive from it,
so a new setting only has to be added here.
"""

CAM_INDEX = 0
CAM_W = 640
CAM_H = 480

SMOOTH_FACTOR = 0.3

PINCH_THRESHOLD = 0.04

CLICK_COOLDOWN = 0.4  # seconds

MAP_X = (0.1, 0.9)  # normalized x range mapped to screen width
MAP_Y = (0.1, 0.9)  # normalized y range mapped to screen height

SCROLL_SENSITIVITY = 10

DRAG_THRESHOLD_SEC = 0.3

DOUBLE_CLICK_WINDOW = 0.35

# Tunable settings, in profile-file key form. Maps setting key -> module attribute.
SETTING_ATTRS = {
    "smooth_factor":       "SMOOTH_FACTOR",
    "pinch_threshold":     "PINCH_THRESHOLD",
    "click_cooldown":      "CLICK_COOLDOWN",
    "scroll_sensitivity":  "SCROLL_SENSITIVITY",
    "drag_threshold":      "DRAG_THRESHOLD_SEC",
    "double_click_window": "DOUBLE_CLICK_WINDOW",
    "map_x":               "MAP_X",
    "map_y":               "MAP_Y",
}

SETTING_KEYS = tuple(SETTING_ATTRS)


def defaults() -> dict:
    """Return the default settings as a plain dict keyed by SETTING_KEYS."""
    return {key: globals()[attr] for key, attr in SETTING_ATTRS.items()}
