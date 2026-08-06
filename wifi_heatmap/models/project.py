from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models.floor import Floor


@dataclass
class Project:
    name: str
    floors: list[Floor] = field(default_factory=list)
    pixels_per_meter: Optional[float] = None
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "target_ssid": "",
            "grid_size": 20,
            "threshold_good": -60,
            "threshold_medium": -75,
            "threshold_poor": -85,
        }
    )
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "floors": [f.to_dict() for f in self.floors],
            "pixels_per_meter": self.pixels_per_meter,
            "settings": self.settings,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            name=data["name"],
            floors=[Floor.from_dict(f) for f in data.get("floors", [])],
            pixels_per_meter=data.get("pixels_per_meter"),
            settings=data.get("settings", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            modified_at=datetime.fromisoformat(data["modified_at"]),
        )

    def save(self, path: str | Path) -> None:
        self.modified_at = datetime.now()
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)
