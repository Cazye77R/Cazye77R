import json
import sys
from pathlib import Path

# When running as a PyInstaller one-file bundle the unpacked files live under
# sys._MEIPASS; fall back to the source tree for normal Python execution.
_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
_DIR  = _BASE / "profiles"

_KEYS = {
    "name", "smooth_factor", "pinch_threshold", "click_cooldown",
    "scroll_sensitivity", "drag_threshold", "double_click_window",
    "map_x", "map_y",
}


def load_profile(name: str) -> dict:
    with open(_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def save_profile(name: str, settings: dict) -> None:
    _DIR.mkdir(exist_ok=True)
    data = {k: settings[k] for k in _KEYS if k in settings}
    data.setdefault("name", name)
    with open(_DIR / f"{name}.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def list_profiles() -> list[str]:
    if not _DIR.exists():
        return []
    return sorted(p.stem for p in _DIR.glob("*.json"))
