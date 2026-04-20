import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

from .models import DrawingAnalysis
from .. import config

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_VALID_MEDIA_TYPES = set(_MIME_TYPES.values()) | {"application/pdf"}

_REQUIRED_FIELDS = {"unit", "base_profile", "extrusion_depth"}

_SYSTEM_PROMPT = (
    "Du bist ein Experte für technische Zeichnungen. "
    "Analysiere die Zeichnung und extrahiere ALLE Geometrien, Maße und Features. "
    "Antworte NUR mit validem JSON ohne Markdown-Backticks. "
    "Halte dich exakt an das vorgegebene Schema."
)

_USER_PROMPT = """\
Analysiere diese technische Zeichnung und antworte NUR mit validem JSON ohne Markdown-Backticks.

Halte dich exakt an dieses Schema (Beispielwerte zeigen den Typ, nicht den Inhalt):
{
  "unit": "mm",
  "view": "front",
  "base_profile": {
    "type": "rectangle",
    "width": 100.0,
    "height": 50.0,
    "thickness": 5.0,
    "radius": null,
    "flange_width": null,
    "flange_height": null,
    "web_thickness": null
  },
  "extrusion_depth": 20.0,
  "holes": [
    {
      "x": 10.0,
      "y": 10.0,
      "diameter": 8.0,
      "depth": "through",
      "depth_value": null,
      "countersink": false,
      "countersink_angle": null
    }
  ],
  "chamfers": [{"edge": "top-front", "distance": 2.0}],
  "fillets":  [{"edge": "bottom-left", "radius": 3.0}],
  "confidence": 0.9,
  "notes": "Freitext-Anmerkungen"
}

Fuer rotationssymmetrische Teile (Wellen, Zylinder, Drehteile) verwende stattdessen:
{
  "base_profile": {
    "type": "revolution",
    "steps": [
      {"diameter": 56.0, "length": 10.0},
      {"diameter": 94.0, "length": 84.0},
      {"diameter": 70.0, "length": 40.0}
    ],
    "bore_diameter": 0.0
  },
  "extrusion_depth": 134.0
}

Erlaubte Werte:
- unit: "mm" | "cm" | "inch"
- base_profile.type: "rectangle" | "circle" | "l" | "t" | "revolution"
- Bei "t" (T-Traeger): width = Flanschbreite (gesamt), height = Gesamthoehe,
  flange_height = Hoehe des UNTEREN Flansches (Basis), web_thickness = Stegdicke
  WICHTIG: flange_height und web_thickness duerfen NICHT 0 sein
- Bei T-Profil mit 3 sichtbaren Abschnitten (Flansch + Steg + oberer Block):
  Falls der obere Block gleich breit oder schmäler als der Steg ist, gehört er
  zum Steg — addiere seine Höhe zur Steghöhe. Nur der BREITESTE untere Abschnitt
  ist der Flansch. flange_height = Höhe des breitesten unteren Abschnitts.
- Bei "l" (Winkelstahl): width = horizontaler Schenkel, height = vertikaler Schenkel,
  flange_height = Materialdicke des horizontalen Schenkels,
  web_thickness = Materialdicke des vertikalen Schenkels
  WICHTIG: flange_height und web_thickness duerfen NICHT 0 sein
- Bei "revolution": steps = Stufenliste von links nach rechts (diameter = Aussendurchmesser),
  bore_diameter = Innendurchmesser (0 falls massiv),
  extrusion_depth = Gesamtlaenge der Welle (= Summe der steps.length)
- holes[].depth: "through" | "blind"
- confidence: 0.0 bis 1.0
"""

# ── Multi-view prompts ─────────────────────────────────────────────────────────

_MULTIVIEW_EXTRACTION_PROMPT = """\
Analysiere diese technische Zeichnung auf Mehrfachansichten.

Schritt 1: Erkenne ob die Zeichnung mehrere Ansichten enthält (Vorder-, Seiten-, Draufsicht).
Schritt 2: Extrahiere für jede Ansicht die sichtbaren Maße und Features.

Antworte NUR mit validem JSON ohne Markdown-Backticks:
{
  "has_multiple_views": true,
  "views_detected": ["front", "side", "top"],
  "unit": "mm",
  "views": {
    "front": {
      "width": 100.0,
      "height": 60.0,
      "profile_type": "rectangle",
      "flange_height": 0.0,
      "flange_width": 0.0,
      "web_thickness": 0.0,
      "holes": [{"x": 15.0, "y": 15.0, "diameter": 8.0, "depth": "through"}],
      "chamfers": [{"edge": "top-front", "distance": 2.0}],
      "fillets": [],
      "features": "Freitext fuer nicht schematisierbare Details"
    },
    "side": {
      "width": 20.0,
      "height": 60.0,
      "profile_type": "rectangle",
      "flange_height": 0.0,
      "flange_width": 0.0,
      "web_thickness": 0.0,
      "holes": [],
      "chamfers": [],
      "fillets": [],
      "features": ""
    },
    "top": {
      "width": 100.0,
      "height": 20.0,
      "profile_type": "rectangle",
      "flange_height": 0.0,
      "flange_width": 0.0,
      "web_thickness": 0.0,
      "holes": [],
      "chamfers": [],
      "fillets": [],
      "features": ""
    }
  }
}

Fuer L-Profile (profile_type="l") und T-Profile (profile_type="t") in der FRONTANSICHT:
  flange_height  = Hoehe des horizontalen Flansches (Grundplatte), z.B. 20.0
  flange_width   = Breite des horizontalen Flansches, z.B. 80.0
  web_thickness  = Dicke des vertikalen Stegs, z.B. 10.0
  width          = Gesamtbreite des Profils (= flange_width fuer T-Profil)
  height         = Gesamthoehe (= flange_height + Steghöhe)
  Bei T-Profil: Falls ein oberer Abschnitt existiert, der gleich breit oder schmäler als
  der Steg ist: Addiere dessen Höhe zur Steghöhe (kein zweiter Flansch).
  flange_height = ausschließlich Höhe des breitesten unteren Abschnitts.

Fuer rotationssymmetrische Teile (Wellen, Zylinder, Drehteile) setze profile_type="revolution"
und ergaenze das View-Objekt der SEITENANSICHT (Profilansicht) um:
  "steps": [{"diameter": 94.0, "length": 84.0}, {"diameter": 70.0, "length": 40.0}, ...],
  "bore_diameter": 0.0,
  "total_length": 184.0

Regeln fuer Wellen (profile_type="revolution"):
- steps: von LINKS nach RECHTS, jede Stufe mit ihrem Aussendurchmesser und ihrer Laenge
- Jede sichtbare Masslinie (z.B. 40, 30, 20) einer konkreten Stufe zuordnen
- Masszahlen in Klammern z.B. (84) = Referenzmaß des dazugehoerigen Abschnitts
- Durchmesser nehmen normalerweise von links nach rechts ab (z.B. 94 → 70 → 56 → 40 → 30)
- total_length = Summe aller steps.length (entspricht der Gesamtlaengenmasslinie)

Regeln:
- Erlaubte Ansichtsbezeichnungen: "front", "side", "top", "back", "bottom", "isometric"
- profile_type: "rectangle" | "circle" | "l" | "t" | "revolution"
- has_multiple_views = false wenn nur eine Ansicht vorhanden (views enthaelt nur "front")
- Alle Masse in der in "unit" angegebenen Einheit
- holes[].depth: "through" | "blind"
- Fehlende Masse als 0.0, fehlende Listen als []
"""

_CONSOLIDATION_SCHEMA = """\
{
  "unit": "mm",
  "view": "multi",
  "base_profile": {
    "type": "rectangle",
    "width": 100.0,
    "height": 60.0,
    "thickness": 0.0,
    "radius": null,
    "flange_width": null,
    "flange_height": null,
    "web_thickness": null
  },
  "extrusion_depth": 20.0,
  "holes": [
    {
      "x": 15.0, "y": 15.0, "diameter": 8.0,
      "depth": "through", "depth_value": null,
      "countersink": false, "countersink_angle": null
    }
  ],
  "chamfers": [{"edge": "top-front", "distance": 2.0}],
  "fillets":  [{"edge": "bottom-left", "radius": 3.0}],
  "confidence": 0.9,
  "notes": "Masse aus N Ansichten konsolidiert. Widersprueche: ..."
}\
"""

_CONSOLIDATION_SCHEMA_REVOLUTION = """\
{
  "unit": "mm",
  "view": "multi",
  "base_profile": {
    "type": "revolution",
    "steps": [
      {"diameter": 94.0, "length": 84.0},
      {"diameter": 70.0, "length": 40.0},
      {"diameter": 56.0, "length": 10.0},
      {"diameter": 40.0, "length": 30.0},
      {"diameter": 30.0, "length": 20.0}
    ],
    "bore_diameter": 0.0
  },
  "extrusion_depth": 184.0,
  "holes": [],
  "chamfers": [{"edge": "step", "distance": 2.0}],
  "fillets":  [],
  "confidence": 0.9,
  "notes": "Welle aus N Ansichten konsolidiert. Gesamtlaenge = Summe aller steps.length."
}\
"""

_CONSOLIDATION_SCHEMA_T = """\
{
  "unit": "mm",
  "view": "multi",
  "base_profile": {
    "type": "t",
    "width": 80.0,
    "height": 60.0,
    "flange_width": 80.0,
    "flange_height": 20.0,
    "web_thickness": 20.0,
    "thickness": 0.0,
    "radius": null
  },
  "extrusion_depth": 40.0,
  "holes": [],
  "chamfers": [{"edge": "top-front", "distance": 2.0}],
  "fillets":  [],
  "confidence": 0.9,
  "notes": "T-Profil aus N Ansichten konsolidiert."
}\
"""

_CONSOLIDATION_SCHEMA_L = """\
{
  "unit": "mm",
  "view": "multi",
  "base_profile": {
    "type": "l",
    "width": 80.0,
    "height": 60.0,
    "flange_width": 80.0,
    "flange_height": 15.0,
    "web_thickness": 15.0,
    "thickness": 0.0,
    "radius": null
  },
  "extrusion_depth": 40.0,
  "holes": [],
  "chamfers": [{"edge": "top-front", "distance": 2.0}],
  "fillets":  [],
  "confidence": 0.9,
  "notes": "L-Profil (Winkelstahl) aus N Ansichten konsolidiert."
}\
"""


class VisionAnalyzer:
    def __init__(self, api_key: str, model: str = None):
        if not api_key or not api_key.strip():
            raise ValueError("api_key darf nicht leer sein.")
        self._api_key = api_key.strip()
        self._model   = model or config.DEFAULT_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_image(self, image_path: str) -> dict:
        """Send image to Claude, return raw parsed JSON dict."""
        encoded, media_type = self._encode_image(image_path)
        payload = self._build_payload(encoded, media_type)
        raw = self._post(payload)
        data = self._extract_json(raw)

        if not self.validate_response(data):
            raise ValueError(
                f"API-Antwort enthält nicht alle Pflichtfelder {_REQUIRED_FIELDS}. "
                f"Erhaltene Schlüssel: {set(data.keys())}"
            )

        self._log_result(data)
        return data

    def analyze(self, image_path: str) -> DrawingAnalysis:
        """Convenience wrapper — returns a typed DrawingAnalysis."""
        return DrawingAnalysis.from_dict(self.analyze_image(image_path))

    def analyze_image_from_base64(
        self, base64_str: str, media_type: str = "image/png"
    ) -> dict:
        """Accept a pre-encoded base64 string (from the HTML palette) and return raw JSON dict.

        Supports image/png, image/jpeg, image/webp and application/pdf.
        PDFs are sent natively as document type — no rasterization required.
        """
        if not base64_str:
            raise ValueError("base64_str darf nicht leer sein.")

        if media_type not in _VALID_MEDIA_TYPES:
            raise ValueError(
                f"Nicht unterstützter MIME-Typ: '{media_type}'. "
                f"Erlaubt: {', '.join(sorted(_VALID_MEDIA_TYPES))}"
            )

        payload = self._build_payload(base64_str, media_type)
        raw = self._post(payload)
        data = self._extract_json(raw)

        if not self.validate_response(data):
            raise ValueError(
                f"API-Antwort enthält nicht alle Pflichtfelder {_REQUIRED_FIELDS}. "
                f"Erhaltene Schlüssel: {set(data.keys())}"
            )

        self._log_result(data)
        return data

    def analyze_multiview_image(self, image_path: str) -> dict:
        """Multi-view pipeline from a file path — detects views then consolidates."""
        encoded, media_type = self._encode_image(image_path)
        return self._multiview_pipeline(encoded, media_type)

    def analyze_multiview_from_base64(
        self, base64_str: str, media_type: str = "image/png"
    ) -> dict:
        """Multi-view pipeline from pre-encoded base64 (from HTML palette).

        Makes two API calls:
          1. View detection + per-view dimension extraction.
          2. Consolidation into a standard DrawingAnalysis JSON (resolves contradictions).
        Falls back gracefully when only one view is detected.
        Supports image/png, image/jpeg, image/webp and application/pdf natively.
        """
        if not base64_str:
            raise ValueError("base64_str darf nicht leer sein.")

        if media_type not in _VALID_MEDIA_TYPES:
            raise ValueError(
                f"Nicht unterstützter MIME-Typ: '{media_type}'. "
                f"Erlaubt: {', '.join(sorted(_VALID_MEDIA_TYPES))}"
            )

        return self._multiview_pipeline(base64_str, media_type)

    def validate_response(self, data: dict) -> bool:
        """Return True when all required top-level fields are present and well-formed."""
        if not isinstance(data, dict):
            return False
        if not _REQUIRED_FIELDS.issubset(data.keys()):
            return False
        profile = data.get("base_profile")
        if not isinstance(profile, dict) or "type" not in profile:
            return False
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encode_image(self, path: str) -> tuple:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Bilddatei nicht gefunden: {path}")

        ext = os.path.splitext(path)[1].lower()
        media_type = _MIME_TYPES.get(ext)
        if media_type is None:
            raise ValueError(
                f"Nicht unterstütztes Bildformat '{ext}'. "
                f"Erlaubt: {', '.join(_MIME_TYPES)}"
            )

        with open(path, "rb") as fh:
            encoded = base64.standard_b64encode(fh.read()).decode("ascii")
        return encoded, media_type

    def _build_payload(self, encoded: str, media_type: str, prompt=None) -> bytes:
        if prompt is None:
            prompt = _USER_PROMPT

        if media_type == "application/pdf":
            content_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": encoded,
                },
            }
        else:
            content_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }

        payload = {
            "model": self._model,
            "max_tokens": config.MAX_TOKENS,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        content_block,
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        return json.dumps(payload).encode("utf-8")

    def _build_text_payload(self, user_text: str) -> bytes:
        """Build a text-only (no image) API payload — used for the consolidation step."""
        payload = {
            "model": self._model,
            "max_tokens": config.MAX_TOKENS,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_text}],
        }
        return json.dumps(payload).encode("utf-8")

    def _multiview_pipeline(self, encoded: str, media_type: str) -> dict:
        # Call 1 — per-view extraction
        payload1 = self._build_payload(encoded, media_type, prompt=_MULTIVIEW_EXTRACTION_PROMPT)
        raw1 = self._post(payload1)
        mv_data = self._extract_json(raw1)

        if not isinstance(mv_data, dict) or "has_multiple_views" not in mv_data:
            raise ValueError(
                f"Ungültige Mehrfachansichten-Antwort von der API.\n"
                f"Erhaltene Schlüssel: {set(mv_data.keys()) if isinstance(mv_data, dict) else type(mv_data)}"
            )

        # Call 2 — consolidation into standard DrawingAnalysis schema
        consolidated = self._consolidate_views(mv_data)

        has_multi = bool(mv_data.get("has_multiple_views"))
        consolidated["multi_view"] = has_multi
        if has_multi:
            views_raw = mv_data.get("views", {})
            consolidated["view_analyses"] = [
                {"view": k, **v} for k, v in views_raw.items()
            ]

        if not self.validate_response(consolidated):
            raise ValueError(
                f"Konsolidierte Antwort enthält nicht alle Pflichtfelder {_REQUIRED_FIELDS}. "
                f"Erhaltene Schlüssel: {set(consolidated.keys())}"
            )

        self._log_result(consolidated)
        return consolidated

    def _consolidate_views(self, mv_data: dict) -> dict:
        """Second API call (text-only): resolve contradictions and produce unified JSON."""
        views_detected = mv_data.get("views_detected", [])
        n = len(views_detected)
        views_json = json.dumps(mv_data, ensure_ascii=False, indent=2)

        # Detect profile type from extraction result
        views = mv_data.get("views", {})
        profile_types = {v.get("profile_type", "").lower() for v in views.values()}
        is_revolution = bool(profile_types & {"revolution", "lathe", "shaft", "welle"})
        is_t_profile  = bool(profile_types & {"t", "tprofile"})
        is_l_profile  = bool(profile_types & {"l", "lprofile"})

        if is_revolution:
            schema = _CONSOLIDATION_SCHEMA_REVOLUTION
            extra_rules = (
                "5. Dieses Bauteil ist ROTATIONSSYMMETRISCH (Welle/Drehteil):\n"
                "   - Nutze die Seitenansicht (Profilansicht) fuer die Stufengeometrie\n"
                "   - Ordne JEDE bemaßte Laenge der richtigen Stufe zu:\n"
                "     * Folge den Pfeillinien der Masszahlen zur zugehoerigen Stufe\n"
                "     * Masszahlen in Klammern (z.B. (84)) = Referenzmaß des Abschnitts\n"
                "     * Durchmesser nehmen i.d.R. von links nach rechts ab\n"
                "   - Berechne fehlende Laengen als Differenz: Gesamtlaenge - Summe bekannter Laengen\n"
                "   - WICHTIG: Summe aller steps.length MUSS = extrusion_depth sein\n"
                "   - bore_diameter nur setzen wenn eine durchgehende Innenbohrung vorhanden\n"
                "   - Die Frontansicht (konzentrische Kreise) bestaetigt nur die Durchmesser,\n"
                "     liefert aber KEINE Laengeninformation\n\n"
            )
        elif is_t_profile:
            schema = _CONSOLIDATION_SCHEMA_T
            extra_rules = (
                "5. Dieses Bauteil ist ein T-PROFIL (Traeger/T-Stueck):\n"
                "   - Nutze die FRONTANSICHT fuer das Querschnittsprofil\n"
                "   - base_profile.type = 't'\n"
                "   - width = Gesamtbreite des Flansches (horizontaler Teil)\n"
                "   - height = Gesamthoehe (= flange_height + web_height)\n"
                "   - flange_height = Hoehe des horizontalen Flansches (Grundplatte)\n"
                "   - flange_width = Breite des Flansches (= width bei symmetrischem T)\n"
                "   - web_thickness = Dicke des vertikalen Stegs\n"
                "   - extrusion_depth = Laenge des Profils (aus der Seitenansicht)\n"
                "   - WICHTIG: Uebernehme flange_height und web_thickness direkt aus den\n"
                "     Frontansicht-Werten, nicht aus width/height der Seitenansicht\n"
                "   - KRITISCH: Falls die Frontansicht 3 Abschnitte zeigt (unten breit, Mitte\n"
                "     schmal, oben schmal gleicher Breite wie Mitte): Der oberste Abschnitt\n"
                "     gehoert zum Steg — addiere seine Hoehe zur Steghöhe. Der Flansch ist\n"
                "     NUR der unterste, breiteste Abschnitt.\n"
                "   - flange_height = Hoehe des untersten breitesten Abschnitts\n"
                "   - height = flange_height + volle Steghöhe inkl. aller deckungsgleichen\n"
                "     Abschnitte oberhalb des Flansches\n"
                "   - web_thickness = Breite des Stegs / der schmaleren Abschnitte\n\n"
            )
        elif is_l_profile:
            schema = _CONSOLIDATION_SCHEMA_L
            extra_rules = (
                "5. Dieses Bauteil ist ein L-PROFIL (Winkelstahl/Winkel):\n"
                "   - Nutze die FRONTANSICHT fuer das Querschnittsprofil\n"
                "   - base_profile.type = 'l'\n"
                "   - width = Breite des horizontalen Schenkels\n"
                "   - height = Hoehe des vertikalen Schenkels\n"
                "   - flange_height = Materialdicke des horizontalen Schenkels\n"
                "   - web_thickness = Materialdicke des vertikalen Schenkels\n"
                "   - extrusion_depth = Laenge des Profils (aus der Seitenansicht)\n"
                "   - WICHTIG: Uebernehme flange_height und web_thickness direkt aus\n"
                "     den Frontansicht-Werten\n\n"
            )
        else:
            schema = _CONSOLIDATION_SCHEMA
            extra_rules = (
                "5. Wenn keine Seitenansicht: schaetze extrusion_depth aus Draufsicht-Hoehe\n\n"
            )

        user_text = (
            "Konsolidiere diese Mehrfachansichten-Analyse zu einer konsistenten DrawingAnalysis.\n\n"
            "Erkannte Ansichten (" + str(n) + "):\n"
            + views_json
            + "\n\nAufgabe:\n"
            "1. Bestimme die Geometrie des Bauteils aus allen Ansichten\n"
            "2. Loese Widersprueche: Falls Masse widersprechen, nutze den haeufigsten Wert\n"
            "   und dokumentiere alle Widersprueche in 'notes'\n"
            "3. Uebernehme Bohrungen aus der Frontansicht (x/y-Koordinaten bleiben)\n"
            "4. Prismatische Koerper: Frontansicht=Breite/Hoehe, Seitenansicht=Tiefe\n"
            + extra_rules
            + "Antworte NUR mit validem JSON ohne Markdown-Backticks, exakt nach diesem Schema:\n"
            + schema
        )

        payload = self._build_text_payload(user_text)
        raw = self._post(payload)
        return self._extract_json(raw)

    def _post(self, payload: bytes) -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        req = urllib.request.Request(_API_URL, data=payload, headers=headers, method="POST")

        print(
            f"[VisionAnalyzer] Sende Request, Größe: {len(payload)} Bytes",
            file=sys.stderr,
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Claude API HTTP {exc.code}: {exc.reason}\n{error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Verbindung zur Claude API fehlgeschlagen: {exc.reason}"
            ) from exc

        try:
            response = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Ungültiges JSON in der API-Antwort: {exc}\nBody: {body[:300]}"
            ) from exc

        if "error" in response:
            err = response["error"]
            raise RuntimeError(
                f"Claude API Fehler [{err.get('type')}]: {err.get('message')}"
            )

        try:
            return response["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(
                f"Unerwartete Antwortstruktur von Claude API: {response}"
            ) from exc

    def _extract_json(self, raw: str) -> dict:
        # Strip optional markdown code fences the model may emit despite instructions
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(
                f"Kein JSON-Objekt in der API-Antwort gefunden.\nAntwort: {raw[:300]}"
            )

        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON konnte nicht geparst werden: {exc}\nRohdaten: {text[start:end][:300]}"
            ) from exc

    def _log_result(self, data: dict):
        confidence = data.get("confidence", 0.0)
        notes = data.get("notes", "")
        views = data.get("view_analyses", [])
        view_info = (
            f" | Ansichten: {len(views)} ({', '.join(v.get('view','?') for v in views)})"
            if views else ""
        )
        message = (
            f"[DrawingToFusion] Analyse abgeschlossen — "
            f"Confidence: {confidence:.0%}"
            + view_info
            + (f" | Notes: {notes}" if notes else "")
        )
        try:
            import adsk.core
            adsk.core.Application.get().log(message)
        except Exception:
            pass
        self.save_last_response(data)

    # last_response.json is written next to the add-in root (DrawingToFusion/)
    _LAST_RESPONSE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "last_response.json",
    )

    def save_last_response(self, response_dict: dict) -> None:
        """Persist response_dict as last_response.json next to the add-in.

        Allows re-running geometry construction from the cached result without
        a repeated (and billable) API call:

            import json
            from DrawingToFusion.core.vision_analyzer import VisionAnalyzer
            data = json.loads(open(VisionAnalyzer._LAST_RESPONSE_PATH).read())["data"]
        """
        payload = {
            "_saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "_model":    self._model,
            "data":      response_dict,
        }
        try:
            with open(self._LAST_RESPONSE_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            try:
                import adsk.core
                adsk.core.Application.get().log(
                    f"[DrawingToFusion] save_last_response fehlgeschlagen: {exc}"
                )
            except Exception:
                pass
