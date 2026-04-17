import adsk.core
import adsk.fusion
import traceback

from .models import DrawingAnalysis, RectangleProfile, CircleProfile, LProfile, TProfile


class GeometryBuilder:
    def __init__(self):
        self._app = adsk.core.Application.get()
        self._ui = self._app.userInterface
        design = adsk.fusion.Design.cast(self._app.activeProduct)
        self._root = design.rootComponent

    def build(self, drawing: DrawingAnalysis):
        f = drawing.to_cm_factor()
        try:
            self._build_profile(drawing, f)
        except Exception:
            self._ui.messageBox(
                f"Fehler beim Erstellen des Profils:\n{traceback.format_exc()}"
            )

    def _build_profile(self, drawing: DrawingAnalysis, f: float):
        profile = drawing.base_profile
        depth = drawing.extrusion_depth * f

        if isinstance(profile, RectangleProfile):
            self._extrude_rect(profile.width * f, profile.height * f, depth)
        elif isinstance(profile, CircleProfile):
            self._extrude_circle(profile.radius * f, depth)
        elif isinstance(profile, (LProfile, TProfile)):
            self._ui.messageBox(
                f"{type(profile).__name__} wird in einer späteren Version unterstützt."
            )
        else:
            self._ui.messageBox("Unbekanntes Profil — kein Körper erstellt.")

    # ------------------------------------------------------------------
    # Sketch + extrude helpers
    # ------------------------------------------------------------------

    def _extrude_rect(self, width: float, height: float, depth: float):
        sketch = self._root.sketches.add(self._root.xYConstructionPlane)
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(width, height, 0),
        )
        self._extrude(sketch, depth)

    def _extrude_circle(self, radius: float, depth: float):
        sketch = self._root.sketches.add(self._root.xYConstructionPlane)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), radius
        )
        self._extrude(sketch, depth)

    def _extrude(self, sketch, depth: float):
        profile = sketch.profiles.item(0)
        self._root.features.extrudeFeatures.addSimple(
            profile,
            adsk.core.ValueInput.createByReal(depth),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
