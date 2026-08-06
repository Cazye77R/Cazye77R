"""Process-global live settings.

Why module-global rather than ``st.session_state``: there is exactly one mouse
and one camera per machine, but ``st.session_state`` is scoped per browser
session. Keeping the live settings here means the main page and the calibration
page see the same values, so a calibration result takes effect immediately
instead of being clobbered by whichever page writes last.

Nothing here imports cv2, pyautogui, mediapipe or streamlit — this module must
stay importable on a headless machine.
"""

import threading

import config
import profile_manager

_lock = threading.RLock()
_settings: dict = config.defaults()
_active_profile: str | None = None

# Non-persisted runtime flags (not part of a profile).
_flags: dict = {"control_active": False}


# ── Settings ──────────────────────────────────────────────────────────────

def snapshot() -> dict:
    """Return a copy of the current settings, safe to read from any thread."""
    with _lock:
        return dict(_settings)


def get(key: str):
    with _lock:
        return _settings[key]


def update(**changes) -> None:
    """Apply one or more setting changes. Unknown keys are rejected loudly."""
    unknown = set(changes) - set(config.SETTING_KEYS)
    if unknown:
        raise KeyError(f"Unbekannte Einstellung(en): {sorted(unknown)}")
    with _lock:
        _settings.update(changes)


def reset_to_defaults() -> None:
    with _lock:
        _settings.clear()
        _settings.update(config.defaults())


# ── Runtime flags ─────────────────────────────────────────────────────────

def flag(name: str, default=None):
    with _lock:
        return _flags.get(name, default)


def set_flag(name: str, value) -> None:
    with _lock:
        _flags[name] = value


# ── Profiles ──────────────────────────────────────────────────────────────

def active_profile() -> str | None:
    with _lock:
        return _active_profile


def apply_profile(name: str) -> dict:
    """Load ``name`` and make it the live settings. Returns the loaded profile."""
    global _active_profile
    profile = profile_manager.load_profile(name)
    with _lock:
        for key in config.SETTING_KEYS:
            if key in profile:
                _settings[key] = profile[key]
        _active_profile = name
    profile_manager.set_active_profile_name(name)
    return profile


def load_startup_profile(preferred: str | None = None) -> str | None:
    """Resolve and apply the profile to start with.

    Order: explicit ``preferred`` -> stored active pointer -> "default".
    Returns the applied profile name, or None when nothing could be loaded
    (in which case the config.py defaults remain in force).
    """
    candidates = [preferred, profile_manager.get_active_profile_name(), "default"]
    for name in candidates:
        if not name:
            continue
        try:
            apply_profile(name)
            return name
        except (FileNotFoundError, ValueError):
            continue
    return None


def as_profile(name: str) -> dict:
    """Build a complete, persistable profile dict from the live settings."""
    with _lock:
        return {"name": name, **{k: _settings[k] for k in config.SETTING_KEYS}}
