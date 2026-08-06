"""Loading, saving and listing gesture profiles.

Two directories are involved:

* **bundled** — read-only seed profiles shipped inside a PyInstaller one-file
  build (``sys._MEIPASS/profiles``). This directory is deleted when the EXE
  exits, so it must never be written to.
* **user** — the writable location. Running from source that is the repo's
  ``profiles/`` directory, so the three tracked JSON files keep working as
  before. In a frozen build it is a per-user config directory, which is what
  makes saved profiles survive a restart.

``HANDCURSOR_HOME`` overrides the user directory (used by the tests).

Stdlib only — this module must stay importable on a headless machine.
"""

import json
import os
import sys
from pathlib import Path

import config

_ACTIVE_FILE = "active_profile.json"

# Keys accepted in a profile file. Derived from config so that adding a setting
# in one place cannot silently fail to persist.
_KEYS = set(config.SETTING_KEYS) | {"name"}


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundled_dir() -> Path | None:
    """Read-only profiles shipped inside the executable, if any."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        return None
    path = Path(meipass) / "profiles"
    return path if path.is_dir() else None


def user_dir() -> Path:
    """Writable profile directory."""
    override = os.environ.get("HANDCURSOR_HOME")
    if override:
        return Path(override) / "profiles"
    if _is_frozen():
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "HandCursor" / "profiles"
    return Path(__file__).resolve().parent / "profiles"


def _search_dirs() -> list[Path]:
    dirs = [user_dir()]
    bundled = bundled_dir()
    if bundled is not None:
        dirs.append(bundled)
    return dirs


# ── Load / save / list ────────────────────────────────────────────────────

def load_profile(name: str) -> dict:
    """Load a profile by name. User directory wins over bundled seeds."""
    if not name:
        raise ValueError("Profilname darf nicht leer sein.")
    for directory in _search_dirs():
        path = directory / f"{name}.json"
        if path.is_file():
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError(f"Profil '{name}' hat kein gültiges Format.")
            return _coerce(data, name)
    raise FileNotFoundError(f"Profil '{name}' nicht gefunden.")


def save_profile(name: str, settings: dict) -> Path:
    """Write a profile to the user directory. Returns the path written."""
    if not name or not name.strip():
        raise ValueError("Profilname darf nicht leer sein.")
    name = name.strip()
    if any(ch in name for ch in '/\\:*?"<>|'):
        raise ValueError(f"Profilname '{name}' enthält unzulässige Zeichen.")

    directory = user_dir()
    directory.mkdir(parents=True, exist_ok=True)
    data = {k: settings[k] for k in _KEYS if k in settings}
    data.setdefault("name", name)
    path = directory / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def list_profiles() -> list[str]:
    """All available profile names, user directory merged with bundled seeds."""
    names: set[str] = set()
    for directory in _search_dirs():
        if directory.is_dir():
            names.update(p.stem for p in directory.glob("*.json")
                         if p.name != _ACTIVE_FILE)
    return sorted(names)


def delete_profile(name: str) -> bool:
    """Remove a user profile. Bundled seeds cannot be deleted."""
    path = user_dir() / f"{name}.json"
    if path.is_file():
        path.unlink()
        return True
    return False


# ── Active-profile pointer ────────────────────────────────────────────────

def get_active_profile_name() -> str | None:
    """Name of the profile last activated, or None if never set."""
    path = user_dir() / _ACTIVE_FILE
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("active") or None
    except (json.JSONDecodeError, OSError):
        return None


def set_active_profile_name(name: str) -> None:
    """Remember ``name`` as the profile to start with next time."""
    directory = user_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / _ACTIVE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"active": name}, fh, indent=2)
    except OSError:
        # A read-only install must not crash the app over a bookkeeping file.
        pass


# ── Validation ────────────────────────────────────────────────────────────

_PAIR_KEYS = ("map_x", "map_y")


def _coerce(data: dict, name: str) -> dict:
    """Drop unknown keys and normalise types; missing keys fall back later."""
    out: dict = {"name": data.get("name", name)}
    for key in config.SETTING_KEYS:
        if key not in data:
            continue
        value = data[key]
        try:
            if key in _PAIR_KEYS:
                lo, hi = (float(v) for v in value)
                if hi <= lo:
                    continue  # degenerate range would divide by zero downstream
                out[key] = (lo, hi)
            elif key == "scroll_sensitivity":
                out[key] = int(value)
            else:
                out[key] = float(value)
        except (TypeError, ValueError):
            continue  # ignore a malformed entry rather than crash on startup
    return out
