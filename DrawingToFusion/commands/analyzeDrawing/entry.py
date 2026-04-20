from __future__ import annotations

import adsk.core
import adsk.fusion
import json
import os
import threading
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


def _resolve_api_key(ui_key: str) -> str:
    """
    Ermittelt den API-Key in folgender Priorität:
    1. Umgebungsvariable ANTHROPIC_API_KEY
    2. Key aus der Palette-UI (ui_key)
    Gibt leeren String zurück wenn keiner gefunden.
    """
    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_key:
        return env_key
    return ui_key.strip()


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
            thread = threading.Thread(
                target=self._run_pipeline,
                args=(data,),
                daemon=True,
                name="DrawingToFusion-Pipeline"
            )
            thread.start()
        except Exception:
            self._send({"type": "error", "message": traceback.format_exc()})

    # ── Pipeline ──────────────────────────────────────────────────────────────
    # ACHTUNG: Alle drei Methoden laufen in einem Background-Thread.
    # Alle Fusion 360 API-Aufrufe (adsk.*) müssen deshalb über
    # GeometryBuilder laufen, der intern executeAsync verwendet.
    # _send() ist threadsafe, da sendInfoToHTML es intern ist.

    def _validate_inputs(self, data: dict):
        """
        Validiert API-Key, Bild und MIME-Typ.
        Gibt (api_key, image_base64, image_mime) zurück oder None bei Fehler.
        """
        api_key      = _resolve_api_key(data.get("apiKey", ""))
        image_base64 = data.get("imageBase64", "")
        image_mime   = data.get("imageMime", "image/png")

        if not api_key:
            self._send({"type": "error", "message": "API-Key fehlt. Bitte eintragen."})
            return None
        if not image_base64:
            self._send({"type": "error", "message": "Kein Bild übermittelt."})
            return None
        if image_mime not in _VALID_MIME:
            self._send({"type": "error", "message": (
                f"MIME-Typ '{image_mime}' nicht unterstützt. "
                "Bitte PNG, JPEG oder WEBP verwenden."
            )})
            return None
        return api_key, image_base64, image_mime

    def _run_vision_analysis(
        self, analyzer: VisionAnalyzer, image_base64: str,
        image_mime: str, multi_view: bool
    ):
        """
        Führt die Vision-Analyse durch (single oder multi-view).
        Gibt result_dict zurück oder None bei Fehler.
        """
        if multi_view:
            self._send({"type": "progress", "step": "Ansichten werden erkannt …", "percent": 20})
            try:
                result_dict = analyzer.analyze_multiview_from_base64(image_base64, image_mime)
            except Exception as exc:
                self._send({"type": "error", "message": f"Mehrfachansichten-Analyse fehlgeschlagen: {exc}"})
                return None
            n_views = len(result_dict.get("view_analyses", []))
            if n_views > 1:
                self._send({"type": "status", "message": f"{n_views} Ansichten erkannt — Maße werden konsolidiert …"})
        else:
            self._send({"type": "progress", "step": "Bild wird analysiert …", "percent": 30})
            try:
                result_dict = analyzer.analyze_image_from_base64(image_base64, image_mime)
            except Exception as exc:
                self._send({"type": "error", "message": f"Analyse fehlgeschlagen: {exc}"})
                return None
        return result_dict

    def _run_pipeline(self, data: dict) -> None:
        # Schritt 1: Validierung
        validated = self._validate_inputs(data)
        if not validated:
            return
        api_key, image_base64, image_mime = validated
        build_holes    = bool(data.get("buildHoles", True))
        build_chamfers = bool(data.get("buildChamfers", True))
        multi_view     = bool(data.get("multiView", False))
        model          = data.get("model", config.DEFAULT_MODEL)

        # Schritt 2: Vision-Analyse
        analyzer    = VisionAnalyzer(api_key, model=model)
        result_dict = self._run_vision_analysis(analyzer, image_base64, image_mime, multi_view)
        if result_dict is None:
            return

        # Schritt 3: Modell aufbauen
        self._send({"type": "progress", "step": "Maße werden geparst …", "percent": 55})
        analysis = DrawingAnalysis.from_dict(result_dict)
        if not build_holes:
            analysis.holes = []
        if not build_chamfers:
            analysis.chamfers = []

        # Schritt 4: Geometrie aufbauen
        self._send({"type": "progress", "step": "Geometrie wird aufgebaut …", "percent": 70})
        try:
            GeometryBuilder().build(analysis)
        except Exception as exc:
            self._send({"type": "error", "message": f"Geometrie-Aufbau fehlgeschlagen: {exc}"})
            return

        # Fertig
        self._send({"type": "progress", "step": "Abgeschlossen.", "percent": 100})
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
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "DrawingToFusion: _send() fehlgeschlagen — Palette möglicherweise geschlossen. Fehler: %s", exc
            )


# ──────────────────────────────────────────────────────────────────────────────
# Palette lifecycle
# ──────────────────────────────────────────────────────────────────────────────

def _show_palette(ui) -> None:
    global _palette

    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..",
        config.PALETTE_URL,
    )
    # Backslashes zu Forward-Slashes konvertieren (Windows-Fix für Chromium)
    html_path = os.path.abspath(html_path).replace("\\", "/")

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
