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

    def _build_payload(self, encoded: str, media_type: str) -> bytes:
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
                        {"type": "text", "text": _USER_PROMPT},
                    ],
                }
            ],
        }
        return json.dumps(payload).encode("utf-8")

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
        message = (
            f"[DrawingToFusion] Analyse abgeschlossen — "
            f"Confidence: {confidence:.0%}"
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
