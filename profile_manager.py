import json
from pathlib import Path

_DIR = Path(__file__).parent / "profiles"

_KEYS = {
    "name", "smooth_factor", "pinch_threshold", "click_cooldown",
    "scroll_sensitivity", "drag_threshold", "double_click_window",
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
