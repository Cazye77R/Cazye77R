"""Vision-based image classification using multimodal Ollama models."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Callable

import ollama

_DEFAULT_CACHE = Path(__file__).parent.parent.parent / "logs" / "vision_cache.json"


class VisionClient:
    def __init__(
        self,
        model: str = "moondream:1.8b",
        base_url: str = "http://localhost:11434",
        cache_path: Path = _DEFAULT_CACHE,
    ) -> None:
        self._model      = model
        self._base_url   = base_url
        self._cache_path = cache_path
        self._cache: dict[str, str] = self._load_cache()
        self._client = ollama.Client(host=base_url)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _load_cache(self) -> dict[str, str]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, image_path: Path) -> str:
        """Return a category string for the image (cached by SHA256)."""
        key = self._sha256(image_path)
        if key in self._cache:
            return self._cache[key]

        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = (
            "Describe this image in one short category label suitable for "
            "a file folder name (1-3 words, no path separators, no slashes). "
            "Reply with the category label only, nothing else."
        )
        resp = self._client.chat(
            model=self._model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [b64],
            }],
        )
        category = resp["message"]["content"].strip().strip('"').strip()
        self._cache[key] = category
        self._save_cache()
        return category

    def classify_batch(
        self,
        images: list[Path],
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> dict[Path, str]:
        """Classify multiple images; returns path → category mapping."""
        results: dict[Path, str] = {}
        total = len(images)
        for i, img in enumerate(images):
            try:
                results[img] = self.classify(img)
            except Exception:
                results[img] = "Sonstiges"
            if progress_cb:
                progress_cb(i + 1, total)
        return results
