from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Dimension:
    label: str
    value: float
    unit: str = "mm"


@dataclass
class Shape:
    shape_type: str          # e.g. "rectangle", "circle", "polygon"
    dimensions: List[Dimension] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    notes: str = ""


@dataclass
class DrawingData:
    title: str = ""
    scale: str = "1:1"
    unit: str = "mm"
    shapes: List[Shape] = field(default_factory=list)
    raw_description: str = ""
