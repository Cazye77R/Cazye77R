"""Persistent user config stored in data/config.json.

Provides a thin key-value API on top of a JSON file so that settings
(last vault path, preferred models, …) survive app restarts without
touching the hard-coded core/config.py defaults.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"


def _load() -> dict[str, Any]:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001
    data = _load()
    data[key] = value
    _save(data)


def update(mapping: dict[str, Any]) -> None:
    data = _load()
    data.update(mapping)
    _save(data)


def delete(key: str) -> None:
    data = _load()
    data.pop(key, None)
    _save(data)


def all_settings() -> dict[str, Any]:
    return _load()
