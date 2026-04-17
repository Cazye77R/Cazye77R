import adsk.core
import adsk.fusion
import traceback

from .models import DrawingData, Shape

CM = 0.1  # mm to cm conversion (Fusion 360 uses cm internally)


class GeometryBuilder:
    def __init__(self):
        self._app = adsk.core.Application.get()
        self._ui = self._app.userInterface
        design = adsk.fusion.Design.cast(self._app.activeProduct)
        self._root = design.rootComponent

    def build(self, drawing: DrawingData):
        for shape in drawing.shapes:
            try:
                self._build_shape(shape)
            except Exception:
                self._ui.messageBox(
                    f"Fehler beim Erstellen von '{shape.shape_type}':\n{traceback.format_exc()}"
                )

    def _build_shape(self, shape: Shape):
        if shape.shape_type == "rectangle":
            self._build_box(shape)
        elif shape.shape_type == "circle":
            self._build_cylinder(shape)
        else:
            self._ui.messageBox(
                f"Form '{shape.shape_type}' wird noch nicht unterstützt."
            )

    def _get_dim(self, shape: Shape, label: str, fallback: float = 10.0) -> float:
        for d in shape.dimensions:
            if d.label.lower() == label.lower():
                return d.value * CM
        return fallback * CM

    def _build_box(self, shape: Shape):
        width = self._get_dim(shape, "width", 10)
        height = self._get_dim(shape, "height", 10)
        depth = self._get_dim(shape, "depth", 10)

        sketches = self._root.sketches
        xy_plane = self._root.xYConstructionPlane
        sketch = sketches.add(xy_plane)

        lines = sketch.sketchCurves.sketchLines
        lines.addTwoPointRectangle(
            adsk.core.Point3D.create(shape.x * CM, shape.y * CM, 0),
            adsk.core.Point3D.create(shape.x * CM + width, shape.y * CM + height, 0),
        )

        profile = sketch.profiles.item(0)
        extrudes = self._root.features.extrudeFeatures
        dist = adsk.core.ValueInput.createByReal(depth)
        extrudes.addSimple(profile, dist, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    def _build_cylinder(self, shape: Shape):
        radius = self._get_dim(shape, "radius", 5)
        height = self._get_dim(shape, "height", 10)

        sketches = self._root.sketches
        xy_plane = self._root.xYConstructionPlane
        sketch = sketches.add(xy_plane)

        circles = sketch.sketchCurves.sketchCircles
        center = adsk.core.Point3D.create(shape.x * CM, shape.y * CM, 0)
        circles.addByCenterRadius(center, radius)

        profile = sketch.profiles.item(0)
        extrudes = self._root.features.extrudeFeatures
        dist = adsk.core.ValueInput.createByReal(height)
        extrudes.addSimple(profile, dist, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
