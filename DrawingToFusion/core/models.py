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


@dataclass
class ThreadSpec:
    """Gewinde auf einer Welle oder in einer Bohrung (DIN ISO 6410)."""
    designation: str          # z.B. "M12x1.5", "M8", "Tr20x4", "G1/2"
    thread_type: str          # "metric" | "metric_fine" | "trapezoidal" | "whitworth" | "pipe"
    start_position: float     # Axiale Position ab Bezugskante in Zeichnungseinheit
    length: float             # Gewindelänge in Zeichnungseinheit
    step_index: int = 0       # Index des RevolutionProfile.steps-Eintrags
    pitch: float = 0.0        # Steigung in mm (0 = Regelgewinde)
    hand: str = "right"       # "right" | "left"
    internal: bool = False    # True = Innengewinde (Bohrung), False = Außengewinde


@dataclass
class UndercutSpec:
    """Freistich an einem Wellenabsatz (DIN 509 Form E/F)."""
    undercut_type: str        # "DIN509_E" | "DIN509_F" | "custom"
    position: float           # Axiale Position in Zeichnungseinheit
    step_index: int = 0       # An welchem Step-Übergang
    width: float = 0.0        # t1 — Breite des Freistichs
    depth: float = 0.0        # t2 — Tiefe des Freistichs
    radius: float = 0.0       # Auslaufradius r


@dataclass
class GrooveSpec:
    """Einstich / Nut auf einer Welle (Sicherungsring, O-Ring, allgemein)."""
    groove_type: str          # "circlip_din471" | "circlip_din472" | "o_ring" | "custom"
    position: float           # Axiale Position in Zeichnungseinheit
    width: float              # Nutbreite
    depth: float              # Nuttiefe (radial)
    step_index: int = 0       # Auf welchem Revolution-Step


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


@dataclass
class RevolutionStep:
    diameter: float    # outer diameter in drawing unit
    length: float      # axial length of this step


@dataclass
class RevolutionProfile(BaseProfile):
    steps: List[RevolutionStep]
    bore_diameter: float = 0.0    # 0 = solid shaft


@dataclass
class ObLongProfile(BaseProfile):
    """Rechteck mit halbkreisförmigen Enden — z.B. Pleuel, Laschen"""
    width: float
    height: float
    radius: float       # Endradius (= height/2 bei echtem Oblong)
    thickness: float = 0.0


@dataclass
class SlotProfile(BaseProfile):
    """Langloch-Aussparung in einem anderen Profil"""
    width: float
    height: float
    radius: float
    x_offset: float = 0.0
    y_offset: float = 0.0


@dataclass
class PolygonProfile(BaseProfile):
    sides: int          # Anzahl Seiten
    diameter: float     # Umkreisdurchmesser
    thickness: float = 0.0


@dataclass
class CompositeProfile(BaseProfile):
    """Beliebige 2D-Kontur als Liste von Punkten + Bögen"""
    sketch_elements: list = field(default_factory=list)
    thickness: float = 0.0


# ---------------------------------------------------------------------------
# Operation model — step-by-step build sequence
# ---------------------------------------------------------------------------

@dataclass
class SketchContour:
    """2D-Kontur als Punktliste für Sketch-Erstellung."""
    points: list = field(default_factory=list)
    closed: bool = True

    @staticmethod
    def from_dict(d: dict) -> "SketchContour":
        return SketchContour(
            points=d.get("points", []),
            closed=d.get("closed", True),
        )


@dataclass
class OperationStep:
    """Ein einzelner Modellierungsschritt in der Build-Sequenz."""
    operation: str = "extrude_add"
    sketch_plane: str = "XY"
    contour: Optional[SketchContour] = None
    depth: float = 0.0
    direction: str = "positive"
    description: str = ""
    hole_diameter: float = 0.0
    hole_x: float = 0.0
    hole_y: float = 0.0
    hole_type: str = "through"
    hole_depth: float = 0.0
    slot_width: float = 0.0
    slot_length: float = 0.0
    slot_x: float = 0.0
    slot_y: float = 0.0
    edge_selection: str = "top"
    size: float = 0.0
    shell_thickness: float = 0.0
    shell_remove_face: str = "top"

    @staticmethod
    def from_dict(d: dict) -> "OperationStep":
        contour_data = d.get("contour")
        return OperationStep(
            operation=d.get("operation", "extrude_add"),
            sketch_plane=d.get("sketch_plane", "XY"),
            contour=SketchContour.from_dict(contour_data) if contour_data else None,
            depth=float(d.get("depth", 0)),
            direction=d.get("direction", "positive"),
            description=d.get("description", ""),
            hole_diameter=float(d.get("hole_diameter", 0)),
            hole_x=float(d.get("hole_x", 0)),
            hole_y=float(d.get("hole_y", 0)),
            hole_type=d.get("hole_type", "through"),
            hole_depth=float(d.get("hole_depth", 0)),
            slot_width=float(d.get("slot_width", 0)),
            slot_length=float(d.get("slot_length", 0)),
            slot_x=float(d.get("slot_x", 0)),
            slot_y=float(d.get("slot_y", 0)),
            edge_selection=d.get("edge_selection", "top"),
            size=float(d.get("size", 0)),
            shell_thickness=float(d.get("shell_thickness", 0)),
            shell_remove_face=d.get("shell_remove_face", "top"),
        )


# ---------------------------------------------------------------------------
# DrawingAnalysis — top-level result returned by VisionAnalyzer
# ---------------------------------------------------------------------------

_CM_FACTORS = {"mm": 0.1, "cm": 1.0, "inch": 2.54}

_PROFILE_KEYS = {
    "rectangle":  RectangleProfile,
    "circle":     CircleProfile,
    "l":          LProfile,
    "lprofile":   LProfile,
    "t":          TProfile,
    "tprofile":   TProfile,
    "revolution": RevolutionProfile,
    "lathe":      RevolutionProfile,
    "shaft":      RevolutionProfile,
    "welle":      RevolutionProfile,
    "oblong":     ObLongProfile,
    "slot":       SlotProfile,
    "polygon":    PolygonProfile,
    "composite":  CompositeProfile,
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
    multi_view: bool = False                # True when consolidated from ≥2 views
    view_analyses: List[dict] = field(default_factory=list)  # raw per-view data
    threads: list = field(default_factory=list)    # List[ThreadSpec]
    undercuts: list = field(default_factory=list)  # List[UndercutSpec]
    grooves: list = field(default_factory=list)    # List[GrooveSpec]
    operations: list = field(default_factory=list) # List[OperationStep]
    modeling_mode: str = "profile"                 # "profile" | "operations"

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

        threads = [
            ThreadSpec(
                designation=t.get("designation", "M6"),
                thread_type=t.get("thread_type", "metric"),
                start_position=float(t.get("start_position", 0)),
                length=float(t.get("length", 10)),
                step_index=int(t.get("step_index", 0)),
                pitch=float(t.get("pitch", 0)),
                hand=t.get("hand", "right"),
                internal=bool(t.get("internal", False)),
            )
            for t in data.get("threads", []) if t
        ]
        undercuts = [
            UndercutSpec(
                undercut_type=u.get("undercut_type", "DIN509_E"),
                position=float(u.get("position", 0)),
                step_index=int(u.get("step_index", 0)),
                width=float(u.get("width", 0)),
                depth=float(u.get("depth", 0)),
                radius=float(u.get("radius", 0)),
            )
            for u in data.get("undercuts", []) if u
        ]
        grooves = [
            GrooveSpec(
                groove_type=g.get("groove_type", "custom"),
                position=float(g.get("position", 0)),
                width=float(g.get("width", 0)),
                depth=float(g.get("depth", 0)),
                step_index=int(g.get("step_index", 0)),
            )
            for g in data.get("grooves", []) if g
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
            multi_view=bool(data.get("multi_view", False)),
            view_analyses=list(data.get("view_analyses", [])),
            threads=threads,
            undercuts=undercuts,
            grooves=grooves,
            operations=[OperationStep.from_dict(op) for op in data.get("operations", []) if op],
            modeling_mode=str(data.get("modeling_mode", "profile")),
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
        if cls is RevolutionProfile:
            steps = []
            for s in d.get("steps", []):
                try:
                    steps.append(RevolutionStep(
                        diameter=float(s.get("diameter", 0)),
                        length=float(s.get("length", 0)),
                    ))
                except (TypeError, ValueError):
                    continue
            if not steps:
                return None
            return RevolutionProfile(
                steps=steps,
                bore_diameter=float(d.get("bore_diameter", 0)),
            )
        if cls is ObLongProfile:
            return ObLongProfile(
                width=float(d.get("width", 0)),
                height=float(d.get("height", 0)),
                radius=float(d.get("radius", 0)),
                thickness=float(d.get("thickness", 0)),
            )
        if cls is SlotProfile:
            return SlotProfile(
                width=float(d.get("width", 0)),
                height=float(d.get("height", 0)),
                radius=float(d.get("radius", 0)),
                x_offset=float(d.get("x_offset", 0)),
                y_offset=float(d.get("y_offset", 0)),
            )
        if cls is PolygonProfile:
            return PolygonProfile(
                sides=int(d.get("sides", 6)),
                diameter=float(d.get("diameter", 0)),
                thickness=float(d.get("thickness", 0)),
            )
        if cls is CompositeProfile:
            return CompositeProfile(
                sketch_elements=list(d.get("sketch_elements", [])),
                thickness=float(d.get("thickness", 0)),
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
