import base64
import datetime
import json
import os
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

Erlaubte Werte:
- unit: "mm" | "cm" | "inch"
- base_profile.type: "rectangle" | "circle" | "l" | "t"
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
      "holes": [{"x": 15.0, "y": 15.0, "diameter": 8.0, "depth": "through"}],
      "chamfers": [{"edge": "top-front", "distance": 2.0}],
      "fillets": [],
      "features": "Freitext fuer nicht schematisierbare Details"
    },
    "side": {
      "width": 20.0,
      "height": 60.0,
      "profile_type": "rectangle",
      "holes": [],
      "chamfers": [],
      "fillets": [],
      "features": ""
    },
    "top": {
      "width": 100.0,
      "height": 20.0,
      "profile_type": "rectangle",
      "holes": [],
      "chamfers": [],
      "fillets": [],
      "features": ""
    }
  }
}

Regeln:
- Erlaubte Ansichtsbezeichnungen: "front", "side", "top", "back", "bottom", "isometric"
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


class VisionAnalyzer:
    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise ValueError("api_key darf nicht leer sein.")
        self._api_key = api_key.strip()

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

        Used instead of analyze_image() when the image is already in memory
        (loaded via FileReader in the browser) rather than on disk.
        """
        if not base64_str:
            raise ValueError("base64_str darf nicht leer sein.")

        valid = set(_MIME_TYPES.values())
        if media_type not in valid:
            raise ValueError(
                f"Nicht unterstützter MIME-Typ: '{media_type}'. "
                f"Erlaubt: {', '.join(sorted(valid))}"
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
        """
        if not base64_str:
            raise ValueError("base64_str darf nicht leer sein.")

        valid = set(_MIME_TYPES.values())
        if media_type not in valid:
            raise ValueError(
                f"Nicht unterstützter MIME-Typ: '{media_type}'. "
                f"Erlaubt: {', '.join(sorted(valid))}"
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
        payload = {
            "model": config.DEFAULT_MODEL,
            "max_tokens": config.MAX_TOKENS,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        return json.dumps(payload).encode("utf-8")

    def _build_text_payload(self, user_text: str) -> bytes:
        """Build a text-only (no image) API payload — used for the consolidation step."""
        payload = {
            "model": config.DEFAULT_MODEL,
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

        user_text = (
            "Konsolidiere diese Mehrfachansichten-Analyse zu einer konsistenten DrawingAnalysis.\n\n"
            "Erkannte Ansichten (" + str(n) + "):\n"
            + views_json
            + "\n\nAufgabe:\n"
            "1. Bestimme die Geometrie des Bauteils aus allen Ansichten:\n"
            "   - Frontansicht: Breite (X) und Hoehe (Y) des Querschnitts\n"
            "   - Seitenansicht: Tiefe des Bauteils (= extrusion_depth)\n"
            "   - Draufsicht: bestaetigt Breite und Tiefe\n"
            "2. Loese Widersprueche: Falls Masse widersprechen, nutze den haeufigsten Wert\n"
            "   und dokumentiere alle Widersprueche in 'notes'\n"
            "3. Uebernehme Bohrungen aus der Frontansicht (x/y-Koordinaten bleiben)\n"
            "4. Wenn keine Seitenansicht: schaetze extrusion_depth aus Draufsicht-Hoehe\n\n"
            "Antworte NUR mit validem JSON ohne Markdown-Backticks, exakt nach diesem Schema:\n"
            + _CONSOLIDATION_SCHEMA
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

        try:
            with urllib.request.urlopen(req) as resp:
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
            "_model":    config.DEFAULT_MODEL,
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
