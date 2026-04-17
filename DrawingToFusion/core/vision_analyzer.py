import base64
import json
import os

from .models import DrawingData, Shape, Dimension
from .. import config


class VisionAnalyzer:
    def __init__(self):
        try:
            import openai
            self._client = openai.OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", config.OPENAI_API_KEY)
            )
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

    def analyze(self, image_path: str) -> DrawingData:
        encoded = self._encode_image(image_path)
        response = self._client.chat.completions.create(
            model=config.VISION_MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analysiere diese technische Zeichnung. "
                                "Gib die Ergebnisse als JSON zurück mit den Feldern: "
                                "title, scale, unit, shapes (Liste mit shape_type, dimensions, x, y, z, notes), "
                                "raw_description. "
                                "Maße in der angegebenen Einheit (Standard: mm)."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
        )

        raw = response.choices[0].message.content
        return self._parse_response(raw)

    def _encode_image(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_response(self, raw: str) -> DrawingData:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return DrawingData(raw_description=raw)

        shapes = []
        for s in data.get("shapes", []):
            dims = [
                Dimension(
                    label=d.get("label", ""),
                    value=float(d.get("value", 0)),
                    unit=d.get("unit", data.get("unit", "mm")),
                )
                for d in s.get("dimensions", [])
            ]
            shapes.append(
                Shape(
                    shape_type=s.get("shape_type", "unknown"),
                    dimensions=dims,
                    x=float(s.get("x", 0)),
                    y=float(s.get("y", 0)),
                    z=float(s.get("z", 0)),
                    notes=s.get("notes", ""),
                )
            )

        return DrawingData(
            title=data.get("title", ""),
            scale=data.get("scale", "1:1"),
            unit=data.get("unit", "mm"),
            shapes=shapes,
            raw_description=data.get("raw_description", raw),
        )
