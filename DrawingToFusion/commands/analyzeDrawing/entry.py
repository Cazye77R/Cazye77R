from __future__ import annotations

import adsk.core
import adsk.fusion
import json
import os
import traceback

from ... import config
from ...core.vision_analyzer import VisionAnalyzer
from ...core.models import DrawingAnalysis
from ...core.geometry_builder import GeometryBuilder

# Kept alive at module level so Fusion's GC doesn't collect them
_handlers: list = []
_palette = None

# MIME types accepted by the Claude messages API (images field)
# application/pdf is allowed — VisionAnalyzer rasterizes it to PNG before the API call
_VALID_MIME = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"})


# ──────────────────────────────────────────────────────────────────────────────
# Command created handler — opens the palette when the toolbar button is clicked
# ──────────────────────────────────────────────────────────────────────────────

class PaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, ui):
        super().__init__()
        self._ui = ui

    def notify(self, args):
        try:
            _show_palette(self._ui)
        except Exception:
            self._ui.messageBox(
                f"Palette konnte nicht geöffnet werden:\n{traceback.format_exc()}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# HTML event handler — receives messages from the JavaScript palette
# ──────────────────────────────────────────────────────────────────────────────

class HTMLEventHandler(adsk.core.HTMLEventHandler):
    def __init__(self, palette, ui):
        super().__init__()
        self._palette = palette
        self._ui = ui

    def notify(self, args):
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            if html_args.action != "analyzeImage":
                return
            data = json.loads(html_args.data)
            self._run_pipeline(data)
        except Exception:
            self._send({"type": "error", "message": traceback.format_exc()})

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _run_pipeline(self, data: dict) -> None:
        api_key        = data.get("apiKey", "").strip()
        image_base64   = data.get("imageBase64", "")
        image_mime     = data.get("imageMime", "image/png")
        build_holes    = bool(data.get("buildHoles", True))
        build_chamfers = bool(data.get("buildChamfers", True))
        multi_view     = bool(data.get("multiView", False))

        # ── Validate inputs ───────────────────────────────────────────────────
        if not api_key:
            self._send({"type": "error", "message": "API-Key fehlt. Bitte in den Einstellungen eintragen."})
            return
        if not image_base64:
            self._send({"type": "error", "message": "Kein Bild übermittelt."})
            return
        if image_mime not in _VALID_MIME:
            self._send({
                "type": "error",
                "message": (
                    f"MIME-Typ '{image_mime}' wird von der Claude API nicht unterstützt. "
                    "Bitte PNG, JPEG oder WEBP verwenden."
                ),
            })
            return

        # ── Step 1: Vision analysis ───────────────────────────────────────────
        analyzer = VisionAnalyzer(api_key)
        if multi_view:
            self._send({"type": "progress", "step": "Ansichten werden erkannt …", "percent": 20})
            try:
                result_dict = analyzer.analyze_multiview_from_base64(image_base64, image_mime)
            except Exception as exc:
                self._send({"type": "error", "message": f"Mehrfachansichten-Analyse fehlgeschlagen: {exc}"})
                return
            n_views = len(result_dict.get("view_analyses", []))
            if n_views > 1:
                self._send({
                    "type": "status",
                    "message": f"{n_views} Ansichten erkannt — Maße werden konsolidiert …",
                })
        else:
            self._send({"type": "progress", "step": "Bild wird analysiert …", "percent": 30})
            try:
                result_dict = analyzer.analyze_image_from_base64(image_base64, image_mime)
            except Exception as exc:
                self._send({"type": "error", "message": f"Analyse fehlgeschlagen: {exc}"})
                return

        # ── Step 2: Parse + honour UI settings ───────────────────────────────
        analysis = DrawingAnalysis.from_dict(result_dict)
        if not build_holes:
            analysis.holes = []
        if not build_chamfers:
            analysis.chamfers = []

        # ── Step 3: Build geometry ────────────────────────────────────────────
        self._send({"type": "progress", "step": "Geometrie wird aufgebaut …", "percent": 70})
        try:
            GeometryBuilder().build(analysis)
        except Exception as exc:
            self._send({"type": "error", "message": f"Geometrie-Aufbau fehlgeschlagen: {exc}"})
            return

        # ── Done ──────────────────────────────────────────────────────────────
        self._send({
            "type":       "success",
            "analysis":   result_dict,
            "confidence": result_dict.get("confidence", 0.0),
        })

    # ── Send helper ───────────────────────────────────────────────────────────

    def _send(self, message: dict) -> None:
        """Send a status/progress/success/error message to the HTML palette."""
        try:
            self._palette.sendInfoToHTML("status", json.dumps(message))
        except Exception:
            pass   # palette may have been closed; silently ignore


# ──────────────────────────────────────────────────────────────────────────────
# Palette lifecycle
# ──────────────────────────────────────────────────────────────────────────────

def _show_palette(ui) -> None:
    global _palette

    html_path = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..",
            config.PALETTE_URL,
        )
    )

    _palette = ui.palettes.itemById(config.PALETTE_ID)

    if not _palette:
        _palette = ui.palettes.add(
            config.PALETTE_ID,
            config.PALETTE_TITLE,
            html_path,
            True,   # isVisible
            True,   # showCloseButton
            True,   # isResizable
            config.PALETTE_WIDTH,
            config.PALETTE_HEIGHT,
        )
        # Register HTML handler once at creation time
        on_html = HTMLEventHandler(_palette, ui)
        _palette.incomingFromHTML.add(on_html)
        _handlers.append(on_html)

    _palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    _palette.isVisible = True


def stop() -> None:
    """Remove the palette and release all event handler references."""
    global _palette
    try:
        app = adsk.core.Application.get()
        palette = app.userInterface.palettes.itemById(config.PALETTE_ID)
        if palette:
            palette.deleteMe()
        _palette = None
    except Exception:
        pass
    _handlers.clear()
