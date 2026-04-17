import base64
import json
import os

from .models import DrawingAnalysis
from .. import config

_SYSTEM_PROMPT = """Du bist ein Experte für technische Zeichnungen.
Analysiere die Zeichnung und antworte ausschließlich mit gültigem JSON.

JSON-Schema:
{
  "unit": "mm|cm|inch",
  "view": "front|top|side|isometric|...",
  "base_profile": {
    "type": "rectangle|circle|l|t",
    "width": <float>, "height": <float>, "thickness": <float>,
    "radius": <float>,
    "flange_width": <float>, "flange_height": <float>, "web_thickness": <float>
  },
  "extrusion_depth": <float>,
  "holes": [
    {"x": <float>, "y": <float>, "diameter": <float>,
     "depth": "through|blind", "depth_value": <float|null>,
     "countersink": <bool>, "countersink_angle": <float|null>}
  ],
  "chamfers": [{"edge": "<beschreibung>", "distance": <float>}],
  "fillets":  [{"edge": "<beschreibung>", "radius": <float>}],
  "confidence": <0.0–1.0>,
  "notes": "<freitext>"
}

Fehlende Felder mit sinnvollen Defaults füllen. Nur JSON zurückgeben, kein Fließtext."""


class VisionAnalyzer:
    def __init__(self):
        try:
            import openai
            self._client = openai.OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", config.OPENAI_API_KEY)
            )
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

    def analyze(self, image_path: str) -> DrawingAnalysis:
        encoded = self._encode_image(image_path)
        response = self._client.chat.completions.create(
            model=config.VISION_MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analysiere diese technische Zeichnung:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
        )

        raw = response.choices[0].message.content
        return self._parse_response(raw)

    def _encode_image(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_response(self, raw: str) -> DrawingAnalysis:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return DrawingAnalysis.from_dict(data)
        except (ValueError, json.JSONDecodeError):
            return DrawingAnalysis(notes=raw)
