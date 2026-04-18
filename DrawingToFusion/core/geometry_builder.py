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

        occ = self._root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        comp = occ.component

        sketch = self._create_base_sketch(comp, analysis, factor)
        extrude = self._extrude(comp, sketch, self._cm(analysis.extrusion_depth, factor))
        body = extrude.bodies.item(0)

        self._add_holes(comp, body, analysis.holes, factor)
        self._add_chamfers(comp, body, analysis.chamfers, factor)
        self._add_fillets(comp, body, analysis.fillets, factor)

    # ──────────────────────────────────────────────────────────────────────
    # Unit conversion
    # ──────────────────────────────────────────────────────────────────────

    def _cm(self, value: float, factor: float) -> float:
        """Convert a value in the drawing's unit to Fusion's internal cm."""
        return value * factor

    # ──────────────────────────────────────────────────────────────────────
    # Sketch creation
    # ──────────────────────────────────────────────────────────────────────

    def _create_base_sketch(
        self, comp, analysis: DrawingAnalysis, factor: float
    ) -> adsk.fusion.Sketch:
        sketch = comp.sketches.add(comp.xYConstructionPlane)
        p = analysis.base_profile

        if isinstance(p, RectangleProfile):
            self._sketch_rectangle(sketch, p, factor)
        elif isinstance(p, CircleProfile):
            self._sketch_circle(sketch, p, factor)
        elif isinstance(p, LProfile):
            self._sketch_l_profile(sketch, p, factor)
        elif isinstance(p, TProfile):
            self._sketch_t_profile(sketch, p, factor)
        else:
            raise ValueError(f"Unbekannter Profiltyp: {type(p).__name__}")

        return sketch

    def _sketch_rectangle(
        self, sketch, profile: RectangleProfile, factor: float
    ) -> None:
        w = self._cm(profile.width,  factor)
        h = self._cm(profile.height, factor)
        t = self._cm(profile.thickness, factor)

        lines = sketch.sketchCurves.sketchLines
        lines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(w, h, 0),
        )
        # When thickness > 0 the rectangle is hollow (box section / shell)
        if t > 0 and t < min(w, h) / 2:
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(t, t, 0),
                adsk.core.Point3D.create(w - t, h - t, 0),
            )

    def _sketch_circle(self, sketch, profile: CircleProfile, factor: float) -> None:
        r = self._cm(profile.radius, factor)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), r
        )

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
        self, comp, sketch, depth_cm: float
    ) -> adsk.fusion.ExtrudeFeature:
        profile = self._largest_profile(sketch)
        extrudes = comp.features.extrudeFeatures
        ext_input = extrudes.createInput(
            profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        extent = adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(depth_cm)
        )
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

    def _add_holes(self, comp, body, holes: list, factor: float) -> None:
        if not holes:
            return
        top_face = self._top_face(body)
        hole_feats = comp.features.holeFeatures

        for spec in holes:
            try:
                self._add_hole(comp, hole_feats, top_face, body, spec, factor)
            except Exception as exc:
                self._ui.messageBox(
                    f"Loch bei ({spec.x}, {spec.y}) übersprungen:\n{exc}"
                )

    def _add_hole(
        self, comp, hole_feats, top_face, body, spec: HoleSpec, factor: float
    ) -> None:
        dia = self._cm(spec.diameter, factor)

        # Sketch point on the top face defines the hole centre
        hole_sk = comp.sketches.add(top_face)
        pt_col = adsk.core.ObjectCollection.create()
        sp = hole_sk.sketchPoints.add(
            adsk.core.Point3D.create(
                self._cm(spec.x, factor), self._cm(spec.y, factor), 0
            )
        )
        pt_col.add(sp)

        if spec.countersink:
            hole_input = hole_feats.createCountersinkInput(
                adsk.core.ValueInput.createByReal(dia)
            )
            if spec.countersink_angle is not None:
                hole_input.counterSinkAngle = adsk.core.ValueInput.createByReal(
                    math.radians(spec.countersink_angle)
                )
        else:
            hole_input = hole_feats.createSimpleInput(
                adsk.core.ValueInput.createByReal(dia)
            )

        hole_input.setPositionBySketchPoints(pt_col)
        hole_input.isDefaultDirection = True
        hole_input.participantBodies = adsk.core.ObjectCollection.createWithArray([body])

        if spec.depth == "blind":
            hole_input.depth = adsk.core.ValueInput.createByReal(
                self._cm(spec.depth_value, factor)
            )

        hole_feats.add(hole_input)

    # ──────────────────────────────────────────────────────────────────────
    # Chamfers
    # ──────────────────────────────────────────────────────────────────────

    def _add_chamfers(self, comp, body, chamfers: list, factor: float) -> None:
        if not chamfers:
            return
        edges = self._top_face_edges(body)
        if edges.count == 0:
            return

        for spec in chamfers:
            try:
                dist = adsk.core.ValueInput.createByReal(
                    self._cm(spec.distance, factor)
                )
                chamfer_input = comp.features.chamferFeatures.createInput(edges, True)
                chamfer_input.setToEqualDistance(dist)
                comp.features.chamferFeatures.add(chamfer_input)
            except Exception as exc:
                self._ui.messageBox(f"Chamfer '{spec.edge}' übersprungen:\n{exc}")

    # ──────────────────────────────────────────────────────────────────────
    # Fillets
    # ──────────────────────────────────────────────────────────────────────

    def _add_fillets(self, comp, body, fillets: list, factor: float) -> None:
        if not fillets:
            return
        edges = self._top_face_edges(body)
        if edges.count == 0:
            return

        for spec in fillets:
            try:
                radius = adsk.core.ValueInput.createByReal(
                    self._cm(spec.radius, factor)
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
        """Return the face whose centroid has the highest Z — the extruded top."""
        top, max_z = None, float('-inf')
        for face in body.faces:
            z = face.centroid.z
            if z > max_z:
                max_z = z
                top = face
        if top is None:
            raise RuntimeError("Kein Face auf dem Body gefunden.")
        return top

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
