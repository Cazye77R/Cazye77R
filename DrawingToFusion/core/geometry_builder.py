from __future__ import annotations

import adsk.core
import adsk.fusion
import datetime
import math
import os

from .models import (
    DrawingAnalysis,
    RectangleProfile,
    CircleProfile,
    LProfile,
    TProfile,
    RevolutionProfile,
    RevolutionStep,
    ObLongProfile,
    SlotProfile,
    PolygonProfile,
    CompositeProfile,
    HoleSpec,
    ChamferSpec,
    FilletSpec,
)

# Fusion 360 user-parameter unit strings for each drawing unit
_UNIT_MAP = {"mm": "mm", "cm": "cm", "inch": "in"}


class GeometryBuilder:
    def __init__(self):
        self._app = adsk.core.Application.get()
        self._ui = self._app.userInterface
        design = adsk.fusion.Design.cast(self._app.activeProduct)
        self._root = design.rootComponent

    # ──────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────

    def build(self, analysis: DrawingAnalysis) -> None:
        if analysis.base_profile is None:
            raise ValueError(
                "DrawingAnalysis enthält kein base_profile — Aufbau abgebrochen."
            )

        p = analysis.base_profile
        factor = analysis.to_cm_factor()
        design = adsk.fusion.Design.cast(self._app.activeProduct)

        if isinstance(p, RevolutionProfile):
            self._build_revolution(design, analysis, p, factor)
            return

        if analysis.extrusion_depth <= 0:
            raise ValueError(
                f"extrusion_depth muss > 0 sein, ist {analysis.extrusion_depth!r}."
            )

        # Create DTF_* user parameters; fall back to raw values if the design
        # is in DirectEdit mode or parameter creation fails for any reason.
        try:
            p_names = self._create_all_parameters(design, analysis)
        except Exception as exc:
            self._app.log(f"[DrawingToFusion] Parameter-Erstellung übersprungen: {exc}")
            p_names = {
                "depth": None,
                "holes":    [{} for _ in analysis.holes],
                "chamfers": [None] * len(analysis.chamfers),
                "fillets":  [None] * len(analysis.fillets),
            }

        comp = self._make_component()

        sketch = self._create_base_sketch(comp, analysis, factor, p_names)

        depth_vi = (
            adsk.core.ValueInput.createByString(p_names["depth"])
            if p_names.get("depth")
            else adsk.core.ValueInput.createByReal(self._cm(analysis.extrusion_depth, factor))
        )
        extrude = self._extrude(comp, sketch, depth_vi)
        body = extrude.bodies.item(0)

        # Hollow-shell: apply Shell feature when a wall thickness is given.
        # This is more reliable than drawing a nested inner rectangle in the
        # sketch, which confuses profile selection and produces wrong geometry.
        if isinstance(p, RectangleProfile) and p.thickness > 0:
            try:
                self._apply_shell(comp, body, p.thickness, factor)
            except Exception as exc:
                self._app.log(f"[DrawingToFusion] Shell übersprungen: {exc}")

        self._add_holes(comp, body, analysis.holes, factor, p_names.get("holes", []))
        self._add_chamfers(comp, body, analysis.chamfers, factor, p_names.get("chamfers", []))
        self._add_fillets(comp, body, analysis.fillets, factor, p_names.get("fillets", []))

    # ──────────────────────────────────────────────────────────────────────
    # Unit conversion
    # ──────────────────────────────────────────────────────────────────────

    def _cm(self, value: float, factor: float) -> float:
        """Convert a value in the drawing's unit to Fusion's internal cm."""
        return value * factor

    def _make_component(self) -> adsk.fusion.Component:
        """Create a new sub-component (Assembly) or fall back to root (Part document).

        Fusion 360 Part documents allow only one component; attempting to add
        a second via addNewComponent() raises error 3. In that case we return
        the root component so geometry is created there directly.
        """
        try:
            occ = self._root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            return occ.component
        except Exception:
            return self._root

    # ──────────────────────────────────────────────────────────────────────
    # User parameters
    # ──────────────────────────────────────────────────────────────────────

    def _ensure_param(
        self, design, name: str, value: float, unit: str, comment: str = ""
    ) -> str:
        """Create or update a DTF_* user parameter; return the parameter name.

        ``value`` is in the drawing's own unit (mm/cm/inch) so the Parameters
        dialog shows human-readable numbers.  Existing parameters are updated
        so that re-running the add-in on a new drawing refreshes the values.
        """
        fu = _UNIT_MAP.get(unit, "mm")
        params = design.userParameters
        existing = params.itemByName(name)
        if existing:
            existing.expression = f"{value} {fu}"
        else:
            vi = adsk.core.ValueInput.createByString(f"{value} {fu}")
            params.add(name, vi, fu, comment)
        return name

    def _create_all_parameters(self, design, analysis: DrawingAnalysis) -> dict:
        """Register all DTF_* user parameters and return a name-lookup dict.

        Return structure::

            {
                "depth":    "DTF_Depth",
                "width":    "DTF_Width",   # profile-specific
                "height":   "DTF_Height",
                "radius":   "DTF_Radius",
                ...
                "holes":    [{"dia": "DTF_HoleDia_1", "x": "DTF_HoleX_1",
                               "y": "DTF_HoleY_1"}, ...],
                "chamfers": ["DTF_ChamferDist_1", ...],
                "fillets":  ["DTF_FilletRad_1", ...],
            }
        """
        u  = analysis.unit
        p  = analysis.base_profile
        ep = self._ensure_param   # shorthand
        pn: dict = {}

        # ── Extrusion depth ────────────────────────────────────────────────
        pn["depth"] = ep(design, "DTF_Depth", analysis.extrusion_depth, u,
                         "DrawingToFusion: extrusion depth")

        # ── Profile dimensions ─────────────────────────────────────────────
        if isinstance(p, RectangleProfile):
            pn["width"]  = ep(design, "DTF_Width",  p.width,  u, "DrawingToFusion: profile width")
            pn["height"] = ep(design, "DTF_Height", p.height, u, "DrawingToFusion: profile height")
            if p.thickness > 0:
                pn["thickness"] = ep(design, "DTF_Thickness", p.thickness, u,
                                     "DrawingToFusion: wall thickness")
        elif isinstance(p, CircleProfile):
            pn["radius"] = ep(design, "DTF_Radius", p.radius, u, "DrawingToFusion: circle radius")
        elif isinstance(p, (LProfile, TProfile)):
            pn["width"]         = ep(design, "DTF_Width",        p.width,         u,
                                     "DrawingToFusion: profile width")
            pn["height"]        = ep(design, "DTF_Height",       p.height,        u,
                                     "DrawingToFusion: profile height")
            pn["flange_height"] = ep(design, "DTF_FlangeHeight", p.flange_height, u,
                                     "DrawingToFusion: flange height")
            pn["web_thickness"] = ep(design, "DTF_WebThickness", p.web_thickness, u,
                                     "DrawingToFusion: web thickness")

        # ── Holes ──────────────────────────────────────────────────────────
        hole_names = []
        for i, hole in enumerate(analysis.holes, 1):
            hpn = {
                "dia": ep(design, f"DTF_HoleDia_{i}", hole.diameter, u,
                          f"DrawingToFusion: hole {i} diameter"),
                "x":   ep(design, f"DTF_HoleX_{i}",   hole.x,        u,
                          f"DrawingToFusion: hole {i} X position"),
                "y":   ep(design, f"DTF_HoleY_{i}",   hole.y,        u,
                          f"DrawingToFusion: hole {i} Y position"),
            }
            if hole.depth == "blind" and hole.depth_value is not None:
                hpn["depth"] = ep(design, f"DTF_HoleDepth_{i}", hole.depth_value, u,
                                  f"DrawingToFusion: hole {i} blind depth")
            hole_names.append(hpn)
        pn["holes"] = hole_names

        # ── Chamfers ───────────────────────────────────────────────────────
        pn["chamfers"] = [
            ep(design, f"DTF_ChamferDist_{i}", ch.distance, u,
               f"DrawingToFusion: chamfer {i} distance")
            for i, ch in enumerate(analysis.chamfers, 1)
        ]

        # ── Fillets ────────────────────────────────────────────────────────
        pn["fillets"] = [
            ep(design, f"DTF_FilletRad_{i}", fi.radius, u,
               f"DrawingToFusion: fillet {i} radius")
            for i, fi in enumerate(analysis.fillets, 1)
        ]

        return pn

    # ──────────────────────────────────────────────────────────────────────
    # Sketch creation
    # ──────────────────────────────────────────────────────────────────────

    def _create_base_sketch(
        self, comp, analysis: DrawingAnalysis, factor: float, p_names: dict
    ) -> adsk.fusion.Sketch:
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        p = analysis.base_profile

        if isinstance(p, RectangleProfile):
            self._sketch_rectangle(sketch, p, factor, p_names)
        elif isinstance(p, CircleProfile):
            self._sketch_circle(sketch, p, factor, p_names)
        elif isinstance(p, LProfile):
            if p.flange_height <= 0 or p.web_thickness <= 0:
                raise ValueError(
                    f"L-Profil: flange_height ({p.flange_height}) und web_thickness ({p.web_thickness}) "
                    "müssen > 0 sein. KI hat unvollständige Werte geliefert."
                )
            self._sketch_l_profile(sketch, p, factor)
        elif isinstance(p, TProfile):
            if p.flange_height <= 0 or p.web_thickness <= 0:
                raise ValueError(
                    f"T-Profil: flange_height ({p.flange_height}) und web_thickness ({p.web_thickness}) "
                    "müssen > 0 sein. KI hat unvollständige Werte geliefert."
                )
            if p.flange_height >= p.height / 2:
                raise ValueError(
                    f"T-Profil: flange_height ({p.flange_height}) >= height/2 ({p.height/2:.1f}). "
                    "Wahrscheinlich wurde der obere Block als Flansch erkannt statt als Teil des Stegs. "
                    "flange_height = nur der unterste, breiteste Abschnitt der Zeichnung."
                )
            self._sketch_t_profile(sketch, p, factor)
        elif isinstance(p, ObLongProfile):
            if p.radius <= 0:
                raise ValueError(
                    f"ObLongProfile: radius ({p.radius}) muss > 0 sein."
                )
            self._build_oblong_sketch(sketch, p, factor)
        elif isinstance(p, SlotProfile):
            if p.radius <= 0:
                raise ValueError(
                    f"SlotProfile: radius ({p.radius}) muss > 0 sein."
                )
            self._build_slot_sketch(sketch, p, factor)
        elif isinstance(p, PolygonProfile):
            if p.sides < 3:
                raise ValueError(
                    f"PolygonProfile: sides ({p.sides}) muss >= 3 sein."
                )
            if p.diameter <= 0:
                raise ValueError(
                    f"PolygonProfile: diameter ({p.diameter}) muss > 0 sein."
                )
            self._build_polygon_sketch(sketch, p, factor)
        elif isinstance(p, CompositeProfile):
            if not p.sketch_elements:
                raise ValueError("CompositeProfile: sketch_elements ist leer.")
            self._build_composite_sketch(sketch, p, factor)
        else:
            raise ValueError(f"Unbekannter Profiltyp: {type(p).__name__}")

        return sketch

    def _sketch_rectangle(
        self, sketch, profile: RectangleProfile, factor: float, p_names: dict
    ) -> None:
        w = self._cm(profile.width,  factor)
        h = self._cm(profile.height, factor)
        t = self._cm(profile.thickness, factor)

        lines = sketch.sketchCurves.sketchLines
        rect_lines = lines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(w, h, 0),
        )

        # ── Sketch constraints ─────────────────────────────────────────────
        # addTwoPointRectangle returns 4 lines: bottom(0), right(1), top(2), left(3).
        # Pin the origin corner so the profile stays anchored when params change.
        try:
            sketch.geometricConstraints.addFixed(rect_lines.item(0).startSketchPoint)
            dims = sketch.sketchDimensions
            HO = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
            VO = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

            # Width: horizontal span of the bottom line
            if p_names.get("width"):
                dim_w = dims.addDistanceDimension(
                    rect_lines.item(0).startSketchPoint,
                    rect_lines.item(0).endSketchPoint,
                    HO,
                    adsk.core.Point3D.create(w / 2, -0.3, 0),
                )
                dim_w.parameter.expression = p_names["width"]

            # Height: vertical span of the right line
            if p_names.get("height"):
                dim_h = dims.addDistanceDimension(
                    rect_lines.item(1).startSketchPoint,
                    rect_lines.item(1).endSketchPoint,
                    VO,
                    adsk.core.Point3D.create(w + 0.3, h / 2, 0),
                )
                dim_h.parameter.expression = p_names["height"]
        except Exception as exc:
            self._app.log(f"[DrawingToFusion] Rechteck-Constraints übersprungen: {exc}")


    def _sketch_circle(
        self, sketch, profile: CircleProfile, factor: float, p_names: dict
    ) -> None:
        r = self._cm(profile.radius, factor)
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), r
        )
        try:
            if p_names.get("radius"):
                dim = sketch.sketchDimensions.addRadialDimension(
                    circle,
                    adsk.core.Point3D.create(r * 0.7, r * 0.7, 0),
                )
                dim.parameter.expression = p_names["radius"]
        except Exception as exc:
            self._app.log(f"[DrawingToFusion] Kreis-Constraint übersprungen: {exc}")

    def _sketch_l_profile(self, sketch, profile: LProfile, factor: float) -> None:
        """
        L-profile (angle iron), origin at bottom-left:

            (0,h) ──── (wt,h)
              │              │
              │         (wt,fh) ──── (w,fh)
              │                          │
            (0,0) ──────────────── (w,0)

        wt = web_thickness  (vertical leg wall)
        fh = flange_height  (horizontal leg wall)
        """
        w  = self._cm(profile.width,         factor)
        h  = self._cm(profile.height,        factor)
        fh = self._cm(profile.flange_height, factor)
        wt = self._cm(profile.web_thickness, factor)

        pts = [
            (0,  0 ),
            (w,  0 ),
            (w,  fh),
            (wt, fh),
            (wt, h ),
            (0,  h ),
        ]
        self._add_closed_polyline(sketch, pts)

    def _sketch_t_profile(self, sketch, profile: TProfile, factor: float) -> None:
        """
        T-profile, flange at bottom, web pointing UP, symmetric around x = w/2:

            (cx-hwt, h) ──── (cx+hwt, h)              ← top of web
                  │                   │
        (0, fh) ──(cx-hwt, fh)  (cx+hwt, fh)── (w, fh)   ← flange top
          │                                          │
        (0,  0) ──────────────────────────── (w,  0)    ← flange bottom

        fh  = flange_height (height of the horizontal base)
        cx  = width / 2
        hwt = web_thickness / 2
        """
        w   = self._cm(profile.width,         factor)
        h   = self._cm(profile.height,        factor)
        fh  = self._cm(profile.flange_height, factor)
        wt  = self._cm(profile.web_thickness, factor)

        cx  = w / 2
        hwt = wt / 2

        pts = [
            (0,        0 ),    # bottom-left of flange
            (w,        0 ),    # bottom-right of flange
            (w,        fh),    # top-right of flange
            (cx + hwt, fh),    # right edge of web at flange top
            (cx + hwt, h ),    # top-right of web
            (cx - hwt, h ),    # top-left of web
            (cx - hwt, fh),    # left edge of web at flange top
            (0,        fh),    # top-left of flange
        ]
        self._add_closed_polyline(sketch, pts)

    def _build_oblong_sketch(self, sketch, profile: ObLongProfile, factor: float) -> None:
        """Two parallel lines + two semicircular arcs forming a closed stadium shape.

        Layout (centered at origin):
            cd = width - 2*radius   (straight section length)
            Arc centers at (±cd/2, 0); arcs sweep -180° (clockwise).
        """
        w  = self._cm(profile.width,  factor)
        r  = self._cm(profile.radius, factor)
        cd = max(w - 2 * r, 0.0)

        lines = sketch.sketchCurves.sketchLines
        arcs  = sketch.sketchCurves.sketchArcs

        if cd > 1e-9:
            lines.addByTwoPoints(
                adsk.core.Point3D.create(-cd / 2,  r, 0),
                adsk.core.Point3D.create( cd / 2,  r, 0),
            )
            lines.addByTwoPoints(
                adsk.core.Point3D.create( cd / 2, -r, 0),
                adsk.core.Point3D.create(-cd / 2, -r, 0),
            )

        # Right semicircle: top → bottom (clockwise = -π)
        arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(cd / 2, 0, 0),
            adsk.core.Point3D.create(cd / 2, r, 0),
            -math.pi,
        )
        # Left semicircle: bottom → top (clockwise = -π)
        arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(-cd / 2, 0, 0),
            adsk.core.Point3D.create(-cd / 2, -r, 0),
            -math.pi,
        )

    def _build_slot_sketch(self, sketch, profile: SlotProfile, factor: float) -> None:
        """Oblong shape offset by (x_offset, y_offset) — same geometry as ObLong."""
        w  = self._cm(profile.width,    factor)
        r  = self._cm(profile.radius,   factor)
        dx = self._cm(profile.x_offset, factor)
        dy = self._cm(profile.y_offset, factor)
        cd = max(w - 2 * r, 0.0)

        lines = sketch.sketchCurves.sketchLines
        arcs  = sketch.sketchCurves.sketchArcs

        if cd > 1e-9:
            lines.addByTwoPoints(
                adsk.core.Point3D.create(dx - cd / 2, dy + r, 0),
                adsk.core.Point3D.create(dx + cd / 2, dy + r, 0),
            )
            lines.addByTwoPoints(
                adsk.core.Point3D.create(dx + cd / 2, dy - r, 0),
                adsk.core.Point3D.create(dx - cd / 2, dy - r, 0),
            )

        arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(dx + cd / 2, dy, 0),
            adsk.core.Point3D.create(dx + cd / 2, dy + r, 0),
            -math.pi,
        )
        arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(dx - cd / 2, dy, 0),
            adsk.core.Point3D.create(dx - cd / 2, dy - r, 0),
            -math.pi,
        )

    def _build_polygon_sketch(self, sketch, profile: PolygonProfile, factor: float) -> None:
        """Regular polygon inscribed in a circle of diameter `profile.diameter`."""
        r = self._cm(profile.diameter / 2.0, factor)
        n = profile.sides
        pts = [
            (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
        self._add_closed_polyline(sketch, pts)

    def _build_composite_sketch(self, sketch, profile: CompositeProfile, factor: float) -> None:
        """Draw arbitrary 2D elements from sketch_elements list.

        Each element dict must have a "type" key:
          {"type": "line",   "x1": …, "y1": …, "x2": …, "y2": …}
          {"type": "arc",    "cx": …, "cy": …, "start_x": …, "start_y": …, "sweep_deg": …}
          {"type": "circle", "cx": …, "cy": …, "radius": …}
        """
        lines   = sketch.sketchCurves.sketchLines
        arcs    = sketch.sketchCurves.sketchArcs
        circles = sketch.sketchCurves.sketchCircles

        for elem in profile.sketch_elements:
            kind = str(elem.get("type", "")).lower()
            try:
                if kind == "line":
                    lines.addByTwoPoints(
                        adsk.core.Point3D.create(
                            self._cm(float(elem.get("x1", 0)), factor),
                            self._cm(float(elem.get("y1", 0)), factor), 0,
                        ),
                        adsk.core.Point3D.create(
                            self._cm(float(elem.get("x2", 0)), factor),
                            self._cm(float(elem.get("y2", 0)), factor), 0,
                        ),
                    )
                elif kind == "arc":
                    arcs.addByCenterStartSweep(
                        adsk.core.Point3D.create(
                            self._cm(float(elem.get("cx", 0)), factor),
                            self._cm(float(elem.get("cy", 0)), factor), 0,
                        ),
                        adsk.core.Point3D.create(
                            self._cm(float(elem.get("start_x", 0)), factor),
                            self._cm(float(elem.get("start_y", 0)), factor), 0,
                        ),
                        math.radians(float(elem.get("sweep_deg", 0))),
                    )
                elif kind == "circle":
                    circles.addByCenterRadius(
                        adsk.core.Point3D.create(
                            self._cm(float(elem.get("cx", 0)), factor),
                            self._cm(float(elem.get("cy", 0)), factor), 0,
                        ),
                        self._cm(float(elem.get("radius", 0)), factor),
                    )
                else:
                    self._app.log(
                        f"[DrawingToFusion] Unbekanntes Composite-Element: {kind!r} — übersprungen."
                    )
            except Exception as exc:
                self._app.log(
                    f"[DrawingToFusion] Composite-Element übersprungen: {exc}"
                )

    # ──────────────────────────────────────────────────────────────────────
    # Revolution (lathe/shaft)
    # ──────────────────────────────────────────────────────────────────────

    def _build_revolution(
        self, design, analysis: DrawingAnalysis, p: RevolutionProfile, factor: float
    ) -> None:
        if not p.steps:
            raise ValueError("RevolutionProfile enthält keine steps.")

        total_len = analysis.extrusion_depth
        if total_len <= 0:
            total_len = sum(s.length for s in p.steps)
        if total_len <= 0:
            raise ValueError("RevolutionProfile: Gesamtlänge = 0.")

        try:
            self._ensure_param(design, "DTF_Depth", total_len, analysis.unit,
                               "DrawingToFusion: shaft total length")
        except Exception as exc:
            self._app.log(f"[DrawingToFusion] Parameter-Erstellung übersprungen: {exc}")

        comp = self._make_component()

        sketch = comp.sketches.add(comp.xYConstructionPlane)
        self._sketch_revolution_profile(sketch, p, factor)

        profile = self._largest_profile(sketch)
        axis = comp.xConstructionAxis
        revolves = comp.features.revolveFeatures
        rev_input = revolves.createInput(
            profile, axis,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        rev_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
        revolves.add(rev_input)

        if analysis.holes:
            self._app.log(
                "[DrawingToFusion] Bohrungen auf Drehteil übersprungen "
                "(Innenprofil via bore_diameter setzen)."
            )
        if analysis.chamfers:
            self._app.log(
                f"[DrawingToFusion] {len(analysis.chamfers)} Fasen auf Drehteil — "
                "bitte manuell hinzufügen."
            )
        if analysis.fillets:
            self._app.log(
                f"[DrawingToFusion] {len(analysis.fillets)} Verrundungen auf Drehteil — "
                "bitte manuell hinzufügen."
            )

    def _sketch_revolution_profile(
        self, sketch, p: RevolutionProfile, factor: float
    ) -> None:
        """Half-section of the shaft: x = axial position, y = radius.
        Revolving around comp.xConstructionAxis (X axis) creates the 3D body.
        """
        bore_r = self._cm(p.bore_diameter / 2.0, factor)
        pts: list = []
        x = 0.0

        # Left face: from axis/bore up to outer radius of first step
        pts.append((x, bore_r if bore_r > 0 else 0.0))

        for i, step in enumerate(p.steps):
            r = self._cm(step.diameter / 2.0, factor)
            length = self._cm(step.length, factor)

            if i == 0:
                pts.append((x, r))   # outer left face
            else:
                prev_r = self._cm(p.steps[i - 1].diameter / 2.0, factor)
                if abs(r - prev_r) > 1e-9:
                    pts.append((x, r))   # step transition face

            if length > 1e-9:
                x += length
                pts.append((x, r))   # outer right face of this step

        # Right face: back down to axis/bore
        pts.append((x, bore_r if bore_r > 0 else 0.0))

        self._add_closed_polyline(sketch, pts)

    def _apply_shell(self, comp, body, thickness: float, factor: float) -> None:
        """Hollow out a solid box by removing its front face (Z=0) and shelling
        with the given wall thickness.  This converts a solid extrusion into a
        five-sided enclosure — the correct shape for a Schaltschrank / housing.
        """
        faces_to_remove = adsk.core.ObjectCollection.create()
        front = self._find_face_at_z(body, 0.0)
        if front is None:
            raise RuntimeError("Shell: Vorderfläche (Z=0) nicht gefunden.")
        faces_to_remove.add(front)
        t_vi = adsk.core.ValueInput.createByReal(self._cm(thickness, factor))
        shell_input = comp.features.shellFeatures.createInput(faces_to_remove, t_vi)
        comp.features.shellFeatures.add(shell_input)

    def _add_closed_polyline(self, sketch, pts: list) -> None:
        lines = sketch.sketchCurves.sketchLines
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            lines.addByTwoPoints(
                adsk.core.Point3D.create(x0, y0, 0),
                adsk.core.Point3D.create(x1, y1, 0),
            )

    # ──────────────────────────────────────────────────────────────────────
    # Extrude
    # ──────────────────────────────────────────────────────────────────────

    def _extrude(
        self, comp, sketch, depth_vi: adsk.core.ValueInput
    ) -> adsk.fusion.ExtrudeFeature:
        profile = self._largest_profile(sketch)
        extrudes = comp.features.extrudeFeatures
        ext_input = extrudes.createInput(
            profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        extent = adsk.fusion.DistanceExtentDefinition.create(depth_vi)
        ext_input.setOneSideExtent(
            extent, adsk.fusion.ExtentDirections.PositiveExtentDirection
        )
        return extrudes.add(ext_input)

    def _largest_profile(self, sketch) -> adsk.fusion.Profile:
        """Select the profile with the greatest area (outermost closed loop)."""
        profiles = sketch.profiles
        if profiles.count == 1:
            return profiles.item(0)
        best, best_area = None, -1.0
        for i in range(profiles.count):
            p = profiles.item(i)
            try:
                area = p.areaProperties().area
            except Exception:
                continue
            if area > best_area:
                best_area = area
                best = p
        if best is None:
            raise RuntimeError("Kein gültiges Skizzenprofil für die Extrusion gefunden.")
        return best

    # ──────────────────────────────────────────────────────────────────────
    # Holes
    # ──────────────────────────────────────────────────────────────────────

    def _add_holes(
        self, comp, body, holes: list, factor: float, hole_p_names: list
    ) -> None:
        if not holes:
            return
        top_face = self._top_face(body)
        hole_feats = comp.features.holeFeatures

        for i, spec in enumerate(holes):
            pn = hole_p_names[i] if i < len(hole_p_names) else {}
            try:
                self._add_hole(comp, hole_feats, top_face, body, spec, factor, pn)
            except Exception as exc:
                self._ui.messageBox(
                    f"Loch bei ({spec.x}, {spec.y}) übersprungen:\n{exc}"
                )

    def _add_hole(
        self,
        comp,
        hole_feats,
        top_face,
        body,
        spec: HoleSpec,
        factor: float,
        p_names_hole: dict,
    ) -> None:
        # Clamp hole centre so it stays at least one radius away from every edge.
        # Holes at x=0 or y=0 (common in AI estimates for edge features like
        # hinges) would otherwise fail or produce invalid geometry.
        bb    = body.boundingBox
        r_cm  = self._cm(spec.diameter / 2.0, factor)
        x_raw = self._cm(spec.x, factor)
        y_raw = self._cm(spec.y, factor)
        x_cm  = max(bb.minPoint.x + r_cm, min(x_raw, bb.maxPoint.x - r_cm))
        y_cm  = max(bb.minPoint.y + r_cm, min(y_raw, bb.maxPoint.y - r_cm))

        # Sketch on the top face — one point per hole centre
        hole_sk = comp.sketches.add(top_face)
        sp = hole_sk.sketchPoints.add(adsk.core.Point3D.create(x_cm, y_cm, 0))

        # Positional constraints driven by DTF_HoleX_n / DTF_HoleY_n
        try:
            if p_names_hole.get("x") and p_names_hole.get("y"):
                origin = hole_sk.originPoint
                dims   = hole_sk.sketchDimensions
                HO     = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
                VO     = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

                dim_x = dims.addDistanceDimension(
                    origin, sp, HO,
                    adsk.core.Point3D.create(x_cm / 2, -0.3, 0),
                )
                dim_x.parameter.expression = p_names_hole["x"]

                dim_y = dims.addDistanceDimension(
                    origin, sp, VO,
                    adsk.core.Point3D.create(-0.3, y_cm / 2, 0),
                )
                dim_y.parameter.expression = p_names_hole["y"]
        except Exception as exc:
            self._app.log(f"[DrawingToFusion] Loch-Position-Constraint übersprungen: {exc}")

        pt_col = adsk.core.ObjectCollection.create()
        pt_col.add(sp)

        # Diameter — parameter expression preferred over raw value
        dia_vi = (
            adsk.core.ValueInput.createByString(p_names_hole["dia"])
            if p_names_hole.get("dia")
            else adsk.core.ValueInput.createByReal(self._cm(spec.diameter, factor))
        )

        if spec.countersink:
            hole_input = hole_feats.createCountersinkInput(dia_vi)
            if spec.countersink_angle is not None:
                hole_input.counterSinkAngle = adsk.core.ValueInput.createByReal(
                    math.radians(spec.countersink_angle)
                )
        else:
            hole_input = hole_feats.createSimpleInput(dia_vi)

        hole_input.setPositionBySketchPoints(pt_col)
        hole_input.isDefaultDirection = True
        hole_input.participantBodies = adsk.core.ObjectCollection.createWithArray([body])

        if spec.depth == "blind":
            depth_vi = (
                adsk.core.ValueInput.createByString(p_names_hole["depth"])
                if p_names_hole.get("depth")
                else adsk.core.ValueInput.createByReal(self._cm(spec.depth_value, factor))
            )
            hole_input.depth = depth_vi

        hole_feats.add(hole_input)

    # ──────────────────────────────────────────────────────────────────────
    # Chamfers
    # ──────────────────────────────────────────────────────────────────────

    def _add_chamfers(
        self, comp, body, chamfers: list, factor: float, chamfer_p_names: list
    ) -> None:
        if not chamfers:
            return
        edges = self._top_face_edges(body)
        if edges.count == 0:
            return

        for i, spec in enumerate(chamfers):
            pn = chamfer_p_names[i] if i < len(chamfer_p_names) else None
            try:
                dist = (
                    adsk.core.ValueInput.createByString(pn)
                    if pn
                    else adsk.core.ValueInput.createByReal(self._cm(spec.distance, factor))
                )
                chamfer_input = comp.features.chamferFeatures.createInput(edges, True)
                chamfer_input.setToEqualDistance(dist)
                comp.features.chamferFeatures.add(chamfer_input)
            except Exception as exc:
                self._ui.messageBox(f"Chamfer '{spec.edge}' übersprungen:\n{exc}")

    # ──────────────────────────────────────────────────────────────────────
    # Fillets
    # ──────────────────────────────────────────────────────────────────────

    def _add_fillets(
        self, comp, body, fillets: list, factor: float, fillet_p_names: list
    ) -> None:
        if not fillets:
            return
        edges = self._top_face_edges(body)
        if edges.count == 0:
            return

        for i, spec in enumerate(fillets):
            pn = fillet_p_names[i] if i < len(fillet_p_names) else None
            try:
                radius = (
                    adsk.core.ValueInput.createByString(pn)
                    if pn
                    else adsk.core.ValueInput.createByReal(self._cm(spec.radius, factor))
                )
                fillet_input = comp.features.filletFeatures.createInput()
                fillet_input.addConstantRadiusEdgeSet(edges, radius, True)
                comp.features.filletFeatures.add(fillet_input)
            except Exception as exc:
                self._ui.messageBox(f"Fillet '{spec.edge}' übersprungen:\n{exc}")

    # ──────────────────────────────────────────────────────────────────────
    # Body / face utilities
    # ──────────────────────────────────────────────────────────────────────

    def _top_face(self, body) -> adsk.fusion.BRepFace:
        """Return the largest flat face on the body — used as the drilling plane.

        For a box extruded from Z=0 in +Z direction the back face (at Z=depth)
        is the largest flat face and the natural plane for through-holes.
        Picking by area rather than Z-centroid works correctly even when the
        Shell feature is applied (which removes the front face at Z=0).
        """
        best, best_area = None, -1.0
        for face in body.faces:
            if face.area > best_area:
                best_area = face.area
                best = face
        if best is None:
            raise RuntimeError("Kein Face auf dem Body gefunden.")
        return best

    def _top_face_edges(self, body) -> adsk.core.ObjectCollection:
        """Collect all edges of the top face into an ObjectCollection."""
        edges = adsk.core.ObjectCollection.create()
        for edge in self._top_face(body).edges:
            edges.add(edge)
        return edges

    _EDGE_Z_TOL = 1e-6   # cm — tolerance for Z-level edge grouping

    def _get_top_edges(self, body) -> adsk.core.ObjectCollection:
        """Return all body edges whose both vertices lie at the highest Z level."""
        try:
            edges = adsk.core.ObjectCollection.create()
            max_z = float('-inf')

            for edge in body.edges:
                for v in (edge.startVertex, edge.endVertex):
                    z = v.geometry.z
                    if z > max_z:
                        max_z = z

            for edge in body.edges:
                zs = edge.startVertex.geometry.z
                ze = edge.endVertex.geometry.z
                if abs(zs - max_z) < self._EDGE_Z_TOL and abs(ze - max_z) < self._EDGE_Z_TOL:
                    edges.add(edge)

            return edges
        except Exception as exc:
            adsk.core.Application.get().userInterface.messageBox(
                f"_get_top_edges fehlgeschlagen:\n{exc}"
            )
            return adsk.core.ObjectCollection.create()

    def _get_bottom_edges(self, body) -> adsk.core.ObjectCollection:
        """Return all body edges whose both vertices lie at the lowest Z level."""
        try:
            edges = adsk.core.ObjectCollection.create()
            min_z = float('inf')

            for edge in body.edges:
                for v in (edge.startVertex, edge.endVertex):
                    z = v.geometry.z
                    if z < min_z:
                        min_z = z

            for edge in body.edges:
                zs = edge.startVertex.geometry.z
                ze = edge.endVertex.geometry.z
                if abs(zs - min_z) < self._EDGE_Z_TOL and abs(ze - min_z) < self._EDGE_Z_TOL:
                    edges.add(edge)

            return edges
        except Exception as exc:
            adsk.core.Application.get().userInterface.messageBox(
                f"_get_bottom_edges fehlgeschlagen:\n{exc}"
            )
            return adsk.core.ObjectCollection.create()

    def _get_largest_face(self, body) -> adsk.fusion.BRepFace:
        """Return the face with the greatest surface area."""
        try:
            best, best_area = None, -1.0
            for face in body.faces:
                if face.area > best_area:
                    best_area = face.area
                    best = face
            if best is None:
                raise RuntimeError("Body enthält keine Faces.")
            return best
        except Exception as exc:
            adsk.core.Application.get().userInterface.messageBox(
                f"_get_largest_face fehlgeschlagen:\n{exc}"
            )
            return None

    def _find_face_at_z(self, body, z_value: float) -> adsk.fusion.BRepFace:
        """Return the face whose centroid Z is closest to z_value."""
        try:
            best, best_dist = None, float('inf')
            for face in body.faces:
                dist = abs(face.centroid.z - z_value)
                if dist < best_dist:
                    best_dist = dist
                    best = face
            if best is None:
                raise RuntimeError("Body enthält keine Faces.")
            return best
        except Exception as exc:
            adsk.core.Application.get().userInterface.messageBox(
                f"_find_face_at_z fehlgeschlagen:\n{exc}"
            )
            return None

    # ──────────────────────────────────────────────────────────────────────
    # Debug
    # ──────────────────────────────────────────────────────────────────────

    # debug.log is written next to the add-in root (DrawingToFusion/)
    _DEBUG_LOG = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "debug.log",
    )

    def debug_dump(self, body) -> None:
        """Dump face/edge/bounding-box info for body to debug.log and the Fusion event log."""
        lines: list[str] = []

        def w(s: str = "") -> None:
            lines.append(s)

        ts = datetime.datetime.now().isoformat(timespec="seconds")
        w("=" * 64)
        w(f"debug_dump  {ts}  —  Body: {body.name}")
        w("=" * 64)

        # ── Bounding box ──────────────────────────────────────────────────
        bb    = body.boundingBox
        lo    = bb.minPoint
        hi    = bb.maxPoint
        sx    = (hi.x - lo.x) * 10   # cm → mm
        sy    = (hi.y - lo.y) * 10
        sz    = (hi.z - lo.z) * 10
        w("")
        w("BoundingBox (mm):")
        w(f"  min   X={lo.x*10:>10.3f}  Y={lo.y*10:>10.3f}  Z={lo.z*10:>10.3f}")
        w(f"  max   X={hi.x*10:>10.3f}  Y={hi.y*10:>10.3f}  Z={hi.z*10:>10.3f}")
        w(f"  size  {sx:.3f} × {sy:.3f} × {sz:.3f} mm")

        # ── Faces ─────────────────────────────────────────────────────────
        w("")
        w(f"Faces ({body.faces.count}):")
        w(f"  {'#':>3}  {'Area cm²':>10}  {'Area mm²':>10}  {'Centroid Z mm':>14}")
        w(f"  {'-'*3}  {'-'*10}  {'-'*10}  {'-'*14}")
        for i in range(body.faces.count):
            face     = body.faces.item(i)
            area_cm2 = face.area
            area_mm2 = area_cm2 * 100          # 1 cm² = 100 mm²
            cz_mm    = face.centroid.z * 10
            w(f"  {i:>3}  {area_cm2:>10.4f}  {area_mm2:>10.2f}  {cz_mm:>14.3f}")

        # ── Edges ─────────────────────────────────────────────────────────
        w("")
        w(f"Edges ({body.edges.count}):")
        w(f"  {'#':>3}  {'Length mm':>10}  {'Start Z mm':>12}  {'End Z mm':>10}")
        w(f"  {'-'*3}  {'-'*10}  {'-'*12}  {'-'*10}")
        for i in range(body.edges.count):
            edge   = body.edges.item(i)
            length = edge.length * 10
            zs     = edge.startVertex.geometry.z * 10
            ze     = edge.endVertex.geometry.z   * 10
            w(f"  {i:>3}  {length:>10.3f}  {zs:>12.3f}  {ze:>10.3f}")

        w("")

        # ── Write to debug.log ────────────────────────────────────────────
        text = "\n".join(lines) + "\n"
        try:
            with open(self._DEBUG_LOG, "a", encoding="utf-8") as fh:
                fh.write(text)
        except Exception as exc:
            self._ui.messageBox(
                f"debug_dump: Log-Datei konnte nicht geschrieben werden:\n"
                f"{self._DEBUG_LOG}\n{exc}"
            )
            return

        # ── Fusion event log (one-line summary) ───────────────────────────
        summary = (
            f"[DrawingToFusion] debug_dump: {body.faces.count} Faces, "
            f"{body.edges.count} Edges, "
            f"BBox {sx:.1f}×{sy:.1f}×{sz:.1f} mm "
            f"→ {self._DEBUG_LOG}"
        )
        try:
            self._app.log(summary)
        except Exception:
            pass
