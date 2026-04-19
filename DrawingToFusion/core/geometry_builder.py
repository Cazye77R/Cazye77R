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
        if analysis.extrusion_depth <= 0:
            raise ValueError(
                f"extrusion_depth muss > 0 sein, ist {analysis.extrusion_depth!r}."
            )

        factor = analysis.to_cm_factor()
        design = adsk.fusion.Design.cast(self._app.activeProduct)

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

        occ = self._root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        comp = occ.component

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
        p = analysis.base_profile
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
            self._sketch_l_profile(sketch, p, factor)
        elif isinstance(p, TProfile):
            self._sketch_t_profile(sketch, p, factor)
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
        T-profile, web pointing down, flange at top, symmetric around x = w/2:

            (0,h) ────────────────────── (w,h)
              │                               │
            (0,wh) ──(cx-hwt,wh)   (cx+hwt,wh)── (w,wh)
                          │                   │
                       (cx-hwt,0)  (cx+hwt,0)

        wh  = web_height = height - flange_height
        cx  = width / 2
        hwt = web_thickness / 2
        """
        w   = self._cm(profile.width,         factor)
        h   = self._cm(profile.height,        factor)
        fh  = self._cm(profile.flange_height, factor)
        wt  = self._cm(profile.web_thickness, factor)

        cx  = w / 2
        hwt = wt / 2
        wh  = h - fh          # height of the vertical web below the flange

        pts = [
            (cx - hwt, 0 ),
            (cx + hwt, 0 ),
            (cx + hwt, wh),
            (w,        wh),
            (w,        h ),
            (0,        h ),
            (0,        wh),
            (cx - hwt, wh),
        ]
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
