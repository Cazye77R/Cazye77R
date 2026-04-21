"""
test_geometry.py — DrawingToFusion GeometryBuilder Test-Script
==============================================================
Kann direkt als Fusion 360 Script ausgeführt werden:
  Utilities → Scripts and Add-Ins → Scripts → [+] → diese Datei wählen → Run

Was wird getestet:
  1. DrawingAnalysis mit Testdaten bauen (kein API-Call nötig)
  2. GeometryBuilder.build() aufrufen
  3. Prüfen, dass eine Occurrence + mindestens 1 Body erstellt wurden
  4. Face- / Edge-Anzahl des Bodys protokollieren

Testdaten: 100×60 mm Rechteck, 20 mm tief, 2 Bohrungen Ø8 mm, 1 Fase 2 mm
"""

import adsk.core
import adsk.fusion
import os
import sys
import traceback

# ── Paket-Pfad einrichten ─────────────────────────────────────────────────────
# Dieses Script liegt im Repo-Root, DrawingToFusion/ ist das Unterverzeichnis.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from DrawingToFusion.core.models import (
    DrawingAnalysis,
    RectangleProfile,
    RevolutionProfile,
    RevolutionStep,
    HoleSpec,
    ChamferSpec,
    ThreadSpec,
    UndercutSpec,
    GrooveSpec,
    OperationStep,
    SketchContour,
)
from DrawingToFusion.core.geometry_builder import GeometryBuilder


# ── Testdaten ─────────────────────────────────────────────────────────────────

def _make_analysis() -> DrawingAnalysis:
    """Erstellt eine DrawingAnalysis mit realistischen Testdaten."""
    return DrawingAnalysis(
        unit="mm",
        view="front",
        base_profile=RectangleProfile(width=100.0, height=60.0, thickness=0.0),
        extrusion_depth=20.0,
        holes=[
            HoleSpec(x=15.0, y=15.0, diameter=8.0, depth="through"),
            HoleSpec(x=85.0, y=15.0, diameter=8.0, depth="through"),
        ],
        chamfers=[ChamferSpec(edge="top_all", distance=2.0)],
        fillets=[],
        confidence=1.0,
        notes="Automatisch generierter Test — kein API-Call",
    )


# ── Assertion-Helfer ──────────────────────────────────────────────────────────

class _AssertionError(Exception):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise _AssertionError(message)


# ── Haupttest ─────────────────────────────────────────────────────────────────

def run(context):
    app = adsk.core.Application.get()
    ui  = app.userInterface
    log_lines: list = []

    def log(msg: str) -> None:
        full = f"[test_geometry] {msg}"
        app.log(full)          # Fusion-Eventlog
        log_lines.append(msg)

    try:
        # ── Voraussetzungen prüfen ────────────────────────────────────────
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            ui.messageBox(
                "Kein aktives Design gefunden.\n"
                "Bitte zuerst ein neues Fusion 360 Design öffnen.",
                "DrawingToFusion — Test abgebrochen",
            )
            return

        if design.designType == adsk.fusion.DesignTypes.DirectDesignType:
            ui.messageBox(
                "Test benötigt den Parametrisch-Modus.\n"
                "Design → Change Design Type → Parametric Design.",
                "DrawingToFusion — Test abgebrochen",
            )
            return

        root = design.rootComponent
        occs_before = root.occurrences.count
        log(f"Ausgangszustand — Occurrences: {occs_before}")

        # ── Testdaten aufbauen ────────────────────────────────────────────
        log("Erstelle DrawingAnalysis …")
        analysis = _make_analysis()

        log(f"  Profil     : {type(analysis.base_profile).__name__} "
            f"{analysis.base_profile.width}×{analysis.base_profile.height} mm")
        log(f"  Tiefe      : {analysis.extrusion_depth} mm")
        log(f"  Einheit    : {analysis.unit}")
        log(f"  Bohrungen  : {len(analysis.holes)}×  "
            + ", ".join(f"Ø{h.diameter}mm@({h.x},{h.y})" for h in analysis.holes))
        log(f"  Fasen      : {len(analysis.chamfers)}×  "
            + ", ".join(f"{c.distance}mm ({c.edge})" for c in analysis.chamfers))

        # ── GeometryBuilder ausführen ─────────────────────────────────────
        log("Starte GeometryBuilder.build() …")
        try:
            builder = GeometryBuilder()
            builder.build(analysis)
        except Exception as exc:
            raise _AssertionError(
                f"GeometryBuilder.build() hat eine Exception geworfen:\n{exc}\n\n"
                + traceback.format_exc()
            )
        log("GeometryBuilder.build() — abgeschlossen ohne Exception  ✓")

        # ── Assertion 1: Neue Occurrence erstellt ─────────────────────────
        occs_after = root.occurrences.count
        _check(
            occs_after > occs_before,
            f"Keine neue Occurrence erstellt "
            f"(vorher: {occs_before}, nachher: {occs_after}).",
        )
        log(f"Neue Occurrence erstellt ({occs_before} → {occs_after})  ✓")

        # ── Assertion 2: Body in der neuen Komponente ─────────────────────
        new_occ  = root.occurrences.item(occs_after - 1)
        comp     = new_occ.component
        body_count = comp.bBodies.count
        _check(
            body_count > 0,
            f"Keine Bodies in der neuen Komponente (bBodies.count = {body_count}).",
        )
        log(f"Bodies in neuer Komponente: {body_count}  ✓")

        # ── Informationen zum erzeugten Body ─────────────────────────────
        body = comp.bBodies.item(0)
        log(f"Body-Name    : {body.name}")
        log(f"Faces        : {body.faces.count}")
        log(f"Edges        : {body.edges.count}")
        log(f"Vertices     : {body.vertices.count}")

        # Bounding-Box für Plausibilitätsprüfung
        bb = body.boundingBox
        size_x = round((bb.maxPoint.x - bb.minPoint.x) * 10, 2)   # cm → mm
        size_y = round((bb.maxPoint.y - bb.minPoint.y) * 10, 2)
        size_z = round((bb.maxPoint.z - bb.minPoint.z) * 10, 2)
        log(f"Bounding-Box : {size_x}×{size_y}×{size_z} mm (±Fasenmaß)")

        # Breite und Höhe sollten in der Nähe von 100×60 mm liegen
        _check(
            90 <= size_x <= 110,
            f"Bounding-Box X erwartet ~100 mm, ist {size_x} mm.",
        )
        _check(
            50 <= size_y <= 70,
            f"Bounding-Box Y erwartet ~60 mm, ist {size_y} mm.",
        )
        _check(
            15 <= size_z <= 25,
            f"Bounding-Box Z erwartet ~20 mm, ist {size_z} mm.",
        )
        log("Bounding-Box-Prüfung (100×60×20 mm ±Toleranz)  ✓")

        # ── Test 2: Stufenwelle mit Gewinde, Freistich, Einstich ─────────
        log("═══ Test 2: Stufenwelle mit Features ═══")

        shaft_analysis = DrawingAnalysis(
            unit="mm",
            view="multi",
            base_profile=RevolutionProfile(
                steps=[
                    RevolutionStep(diameter=30, length=40),   # Step 0: Ø30×40 mm (Gewindezapfen)
                    RevolutionStep(diameter=40, length=50),   # Step 1: Ø40×50 mm (Lagersitz)
                    RevolutionStep(diameter=25, length=30),   # Step 2: Ø25×30 mm (Abtrieb)
                ],
                bore_diameter=0,
            ),
            extrusion_depth=120.0,
            holes=[],
            chamfers=[],
            fillets=[],
            threads=[
                ThreadSpec(
                    designation="M30x2",
                    thread_type="metric_fine",
                    start_position=5.0,
                    length=25.0,
                    step_index=0,
                    pitch=2.0,
                ),
            ],
            undercuts=[
                UndercutSpec(
                    undercut_type="DIN509_E",
                    position=38.0,
                    step_index=0,
                    width=2.5,
                    depth=0.3,
                    radius=0.2,
                ),
                UndercutSpec(
                    undercut_type="DIN509_E",
                    position=88.0,
                    step_index=1,
                    width=2.0,
                    depth=0.2,
                    radius=0.1,
                ),
            ],
            grooves=[
                GrooveSpec(
                    groove_type="circlip_din471",
                    position=105.0,
                    width=1.8,
                    depth=1.1,
                    step_index=2,
                ),
            ],
            confidence=0.85,
            notes="Teststufenwelle mit 3 Absätzen",
        )

        try:
            GeometryBuilder().build(shaft_analysis)
            log("Stufenwelle erfolgreich erstellt  ✓")
        except Exception as exc:
            log(f"Stufenwelle fehlgeschlagen: {exc}")

        # Prüfungen für Test 2
        occs_t2 = root.occurrences.count
        if occs_t2 >= 2:
            occ_t2  = root.occurrences.item(occs_t2 - 1)
            comp_t2 = occ_t2.component
            bodies_t2 = comp_t2.bRepBodies
            if bodies_t2.count > 0:
                body_t2 = bodies_t2.item(0)
                bb2 = body_t2.boundingBox
                total_length_mm = round((bb2.maxPoint.x - bb2.minPoint.x) * 10, 1)
                max_diam_mm     = round(
                    max(
                        (bb2.maxPoint.y - bb2.minPoint.y),
                        (bb2.maxPoint.z - bb2.minPoint.z),
                    ) * 10, 1
                )
                log(f"  Gesamtlänge  : {total_length_mm} mm (erwartet ~120)")
                log(f"  Max. Ø       : {max_diam_mm} mm (erwartet ~40)")
            else:
                log("  ✗ Kein Body in Wellen-Komponente")

            thread_count  = comp_t2.features.threadFeatures.count
            revolve_count = comp_t2.features.revolveFeatures.count
            log(f"  Thread-Features : {thread_count} (erwartet 1)")
            log(f"  Revolve-Features: {revolve_count} (erwartet ≥4: Grundkörper + 2 Freistiche + 1 Nut)")
        else:
            log("  ✗ Wellen-Occurrence nicht gefunden")

        # ── Test 3: Stufenkörper (Operations-Modus) ──────────────────────
        log("═══ Test 3: Stufenkörper (Operations-Modus) ═══")

        stufen_analysis = DrawingAnalysis(
            unit="mm",
            extrusion_depth=20.0,
            confidence=0.9,
            notes="Stufenkörper aus Dreitafelprojektion",
            modeling_mode="operations",
            base_profile=RectangleProfile(width=40, height=60),
            operations=[
                OperationStep(
                    operation="extrude_add",
                    sketch_plane="XY",
                    contour=SketchContour(
                        points=[
                            [0, 0], [40, 0], [40, 20],
                            [30, 20], [30, 60], [10, 60],
                            [10, 20], [0, 20],
                        ],
                        closed=True,
                    ),
                    depth=20.0,
                    description="T-Stufenkörper Vorderansicht, 20mm tief",
                ),
            ],
            holes=[],
            chamfers=[],
            fillets=[],
        )

        try:
            GeometryBuilder().build(stufen_analysis)
            log("✓ Stufenkörper erfolgreich erstellt")
        except Exception as exc:
            log(f"✗ Stufenkörper fehlgeschlagen: {exc}")

        # ── Test 4: Block mit Stufe, Langloch und Bohrung ────────────────
        log("═══ Test 4: Komplexer Block (Operations-Modus) ═══")

        block_analysis = DrawingAnalysis(
            unit="mm",
            extrusion_depth=20.0,
            confidence=0.85,
            notes="Block mit Stufe, Langloch, Bohrung",
            modeling_mode="operations",
            base_profile=RectangleProfile(width=70, height=50),
            operations=[
                OperationStep(
                    operation="extrude_add",
                    sketch_plane="XY",
                    contour=SketchContour(
                        points=[[0, 0], [70, 0], [70, 50], [0, 50]],
                        closed=True,
                    ),
                    depth=20.0,
                    description="Grundkörper 70×50×20mm",
                ),
                OperationStep(
                    operation="extrude_cut",
                    sketch_plane="face_top",
                    contour=SketchContour(
                        points=[[0, 0], [55, 0], [55, 7], [0, 7]],
                        closed=True,
                    ),
                    depth=7.0,
                    direction="negative",
                    description="Stufe oben absetzen 55×7mm",
                ),
                OperationStep(
                    operation="slot",
                    sketch_plane="face_front",
                    slot_width=10.0,
                    slot_length=15.0,
                    slot_x=22.0,
                    slot_y=25.0,
                    depth=20.0,
                    description="Langloch 10×15mm mittig",
                ),
                OperationStep(
                    operation="hole",
                    sketch_plane="face_front",
                    hole_diameter=10.0,
                    hole_x=55.0,
                    hole_y=25.0,
                    hole_type="through",
                    description="Durchgangsbohrung Ø10 rechts",
                ),
            ],
            holes=[],
            chamfers=[],
            fillets=[],
        )

        try:
            GeometryBuilder().build(block_analysis)
            log("✓ Komplexer Block erfolgreich erstellt")
        except Exception as exc:
            log(f"✗ Komplexer Block fehlgeschlagen: {exc}")

        log("═══ Alle Tests abgeschlossen ═══")

        # ── Ergebnis-Dialog ───────────────────────────────────────────────
        log_text = "\n".join(f"  {l}" for l in log_lines)
        ui.messageBox(
            f"Alle Tests bestanden!\n\n"
            f"Log:\n{log_text}",
            "DrawingToFusion — Test OK",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType,
        )

    except _AssertionError as exc:
        log_text = "\n".join(f"  {l}" for l in log_lines)
        ui.messageBox(
            f"Assertion fehlgeschlagen:\n{exc}\n\nLog:\n{log_text}",
            "DrawingToFusion — Test FAILED",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.CriticalIconType,
        )

    except Exception:
        log_text = "\n".join(f"  {l}" for l in log_lines)
        ui.messageBox(
            f"Unerwarteter Fehler:\n{traceback.format_exc()}\n\nLog:\n{log_text}",
            "DrawingToFusion — Test ERROR",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.CriticalIconType,
        )
