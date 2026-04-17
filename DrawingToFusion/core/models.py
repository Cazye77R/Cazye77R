from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Feature specs
# ---------------------------------------------------------------------------

@dataclass
class HoleSpec:
    x: float
    y: float
    diameter: float
    depth: str = "through"          # "through" | "blind"
    depth_value: Optional[float] = None
    countersink: bool = False
    countersink_angle: Optional[float] = None

    def __post_init__(self):
        if self.depth not in ("through", "blind"):
            raise ValueError(f"HoleSpec.depth must be 'through' or 'blind', got {self.depth!r}")
        if self.depth == "blind" and self.depth_value is None:
            raise ValueError("HoleSpec.depth_value is required when depth='blind'")
        if self.countersink and self.countersink_angle is None:
            self.countersink_angle = 90.0


@dataclass
class ChamferSpec:
    edge: str
    distance: float


@dataclass
class FilletSpec:
    edge: str
    radius: float


# ---------------------------------------------------------------------------
# Base profile + concrete subclasses
# ---------------------------------------------------------------------------

@dataclass
class BaseProfile:
    """Abstract base — never instantiate directly."""


@dataclass
class RectangleProfile(BaseProfile):
    width: float
    height: float
    thickness: float = 0.0      # used for L/T cross-section plate thickness


@dataclass
class CircleProfile(BaseProfile):
    radius: float


@dataclass
class LProfile(BaseProfile):
    width: float
    height: float
    flange_width: float
    flange_height: float
    web_thickness: float


@dataclass
class TProfile(BaseProfile):
    width: float
    height: float
    flange_width: float
    flange_height: float
    web_thickness: float


# ---------------------------------------------------------------------------
# DrawingAnalysis — top-level result returned by VisionAnalyzer
# ---------------------------------------------------------------------------

_CM_FACTORS = {"mm": 0.1, "cm": 1.0, "inch": 2.54}

_PROFILE_KEYS = {
    "rectangle": RectangleProfile,
    "circle": CircleProfile,
    "l": LProfile,
    "lprofile": LProfile,
    "t": TProfile,
    "tprofile": TProfile,
}


@dataclass
class DrawingAnalysis:
    unit: str = "mm"                        # "mm" | "cm" | "inch"
    view: str = ""
    base_profile: Optional[BaseProfile] = None
    extrusion_depth: float = 0.0
    holes: List[HoleSpec] = field(default_factory=list)
    chamfers: List[ChamferSpec] = field(default_factory=list)
    fillets: List[FilletSpec] = field(default_factory=list)
    confidence: float = 0.0                 # 0.0–1.0
    notes: str = ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_cm_factor(self) -> float:
        """Return the multiplier that converts this drawing's unit to cm."""
        return _CM_FACTORS.get(self.unit, 0.1)

    # ------------------------------------------------------------------
    # JSON → DrawingAnalysis
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> DrawingAnalysis:
        unit = data.get("unit", "mm")
        if unit not in _CM_FACTORS:
            unit = "mm"

        base_profile = _parse_profile(data.get("base_profile") or data.get("profile") or {})

        holes = [_parse_hole(h) for h in data.get("holes", []) if h]
        chamfers = [
            ChamferSpec(edge=str(c.get("edge", "")), distance=float(c.get("distance", 0)))
            for c in data.get("chamfers", []) if c
        ]
        fillets = [
            FilletSpec(edge=str(f.get("edge", "")), radius=float(f.get("radius", 0)))
            for f in data.get("fillets", []) if f
        ]

        return cls(
            unit=unit,
            view=str(data.get("view", "")),
            base_profile=base_profile,
            extrusion_depth=float(data.get("extrusion_depth", 0)),
            holes=holes,
            chamfers=chamfers,
            fillets=fillets,
            confidence=min(1.0, max(0.0, float(data.get("confidence", 0)))),
            notes=str(data.get("notes", "")),
        )


# ---------------------------------------------------------------------------
# Private parsing helpers
# ---------------------------------------------------------------------------

def _parse_profile(d: dict) -> Optional[BaseProfile]:
    if not d:
        return None

    kind = str(d.get("type", "")).lower().replace("-", "").replace("_", "")
    cls = _PROFILE_KEYS.get(kind)
    if cls is None:
        return None

    try:
        if cls is RectangleProfile:
            return RectangleProfile(
                width=float(d.get("width", 0)),
                height=float(d.get("height", 0)),
                thickness=float(d.get("thickness", 0)),
            )
        if cls is CircleProfile:
            return CircleProfile(radius=float(d.get("radius", 0)))
        if cls in (LProfile, TProfile):
            return cls(
                width=float(d.get("width", 0)),
                height=float(d.get("height", 0)),
                flange_width=float(d.get("flange_width", 0)),
                flange_height=float(d.get("flange_height", 0)),
                web_thickness=float(d.get("web_thickness", 0)),
            )
    except (TypeError, ValueError):
        return None

    return None


def _parse_hole(d: dict) -> Optional[HoleSpec]:
    try:
        depth = str(d.get("depth", "through"))
        if depth not in ("through", "blind"):
            depth = "through"

        depth_value = d.get("depth_value")
        if depth_value is not None:
            depth_value = float(depth_value)

        countersink_angle = d.get("countersink_angle")
        if countersink_angle is not None:
            countersink_angle = float(countersink_angle)

        return HoleSpec(
            x=float(d.get("x", 0)),
            y=float(d.get("y", 0)),
            diameter=float(d.get("diameter", 0)),
            depth=depth,
            depth_value=depth_value,
            countersink=bool(d.get("countersink", False)),
            countersink_angle=countersink_angle,
        )
    except (TypeError, ValueError):
        return None
