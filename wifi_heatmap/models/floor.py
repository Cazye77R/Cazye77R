from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from models.measurement import Measurement


@dataclass
class Floor:
    name: str
    level: int = 0
    background_image: Optional[str] = None
    bg_offset: tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    bg_scale: float = 1.0
    elements: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    router_position: Optional[tuple[float, float]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level,
            "background_image": self.background_image,
            "bg_offset": list(self.bg_offset),
            "bg_scale": self.bg_scale,
            "elements": self.elements,
            "measurements": [m.to_dict() for m in self.measurements],
            "router_position": list(self.router_position) if self.router_position else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Floor":
        router_raw = data.get("router_position")
        return cls(
            name=data["name"],
            level=data.get("level", 0),
            background_image=data.get("background_image"),
            bg_offset=tuple(data.get("bg_offset", [0.0, 0.0])),  # type: ignore[arg-type]
            bg_scale=data.get("bg_scale", 1.0),
            elements=data.get("elements", []),
            measurements=[Measurement.from_dict(m) for m in data.get("measurements", [])],
            router_position=tuple(router_raw) if router_raw else None,  # type: ignore[arg-type]
        )
