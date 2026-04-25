"""StockMind – NVIDIA NIM LLM Provider (OpenAI-kompatibel)."""
from __future__ import annotations

import os
import sys

import requests

# stockmind/ in sys.path damit from modules.logger funktioniert
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.llm_providers.base import LLMProvider  # noqa: E402
from modules.logger import logger  # noqa: E402

_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"
_NIM_TIMEOUT_S = 60


class NvidiaProvider(LLMProvider):
    def __init__(self) -> None:
        # Dynamisch lesen – kein Caching, damit Runtime-Wechsel möglich ist
        self._api_key: str = os.environ.get("NVIDIA_API_KEY", "")
        self._model: str = os.environ.get("NVIDIA_MODEL", _DEFAULT_MODEL)

    # ------------------------------------------------------------------
    # health / status
    # ------------------------------------------------------------------

    def health(self) -> bool:
        return self._api_key.startswith("nvapi-")

    def get_status(self) -> dict:
        if not self.health():
            return {
                "running": False,
                "url": _NIM_URL,
                "model_count": 0,
                "error": (
                    "NVIDIA_API_KEY nicht gesetzt oder ungültig "
                    "(muss mit 'nvapi-' beginnen)."
                ),
                "install_guide": (
                    "API-Key unter https://build.nvidia.com/ erstellen "
                    "und als NVIDIA_API_KEY in .env eintragen."
                ),
            }
        return {
            "running": True,
            "url": _NIM_URL,
            "model_count": 1,
            "error": "",
            "install_guide": "",
        }

    # ------------------------------------------------------------------
    # models
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        return [self._model]

    def list_models_with_info(self) -> list[dict]:
        return [{
            "name": self._model,
            "full_name": self._model,
            "size_gb": 0.0,
            "modified": "",
            "description": "NVIDIA NIM Cloud API",
        }]

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.2,
        **kwargs,
    ) -> str:
        active_model = model or self._model
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": active_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        logger.debug(f"NvidiaProvider.chat model={active_model} msgs={len(messages)}")
        resp = requests.post(
            _NIM_URL,
            headers=headers,
            json=payload,
            timeout=_NIM_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
