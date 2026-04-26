"""StockMind – Ollama LLM Provider."""
from __future__ import annotations

import os
import sys

import requests

# stockmind/ in sys.path damit from config / from modules.logger funktioniert
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config import MODEL_DESCRIPTIONS, OLLAMA_BASE_URL, OLLAMA_TIMEOUT_S  # noqa: E402

from modules.llm_providers.base import LLMProvider  # noqa: E402
from modules.logger import logger  # noqa: E402

_INSTALL_GUIDE = """
**Ollama ist nicht erreichbar.**

Installation:
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# → https://ollama.ai/download/windows
```

Dienst starten:
```bash
ollama serve
```

Erstes Modell laden:
```bash
ollama pull llama3
```
""".strip()


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self._base_url: str = OLLAMA_BASE_URL
        self._timeout: int = OLLAMA_TIMEOUT_S

    # ------------------------------------------------------------------
    # health / status
    # ------------------------------------------------------------------

    def health(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug(f"Ollama nicht erreichbar: {exc}")
            return False

    def get_status(self) -> dict:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=3)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return {
                "running": True,
                "url": self._base_url,
                "model_count": len(models),
                "error": "",
                "install_guide": "",
            }
        except requests.exceptions.ConnectionError:
            return {
                "running": False,
                "url": self._base_url,
                "model_count": 0,
                "error": f"Verbindung zu {self._base_url} abgelehnt.",
                "install_guide": _INSTALL_GUIDE,
            }
        except requests.exceptions.Timeout:
            return {
                "running": False,
                "url": self._base_url,
                "model_count": 0,
                "error": f"Timeout beim Verbinden mit {self._base_url} (>3s).",
                "install_guide": _INSTALL_GUIDE,
            }
        except Exception as exc:
            return {
                "running": False,
                "url": self._base_url,
                "model_count": 0,
                "error": str(exc),
                "install_guide": _INSTALL_GUIDE,
            }

    # ------------------------------------------------------------------
    # models
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        except Exception as exc:
            logger.debug(f"OllamaProvider.list_models fehlgeschlagen: {exc}")
            return []

    def list_models_with_info(self) -> list[dict]:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            result = []
            for m in resp.json().get("models", []):
                name = m["name"].split(":")[0]
                size_bytes = m.get("size", 0)
                result.append({
                    "name": name,
                    "full_name": m["name"],
                    "size_gb": round(size_bytes / 1024**3, 2) if size_bytes else 0.0,
                    "modified": m.get("modified_at", "")[:10],
                    "description": MODEL_DESCRIPTIONS.get(name, ""),
                })
            return result
        except Exception as exc:
            logger.debug(f"OllamaProvider.list_models_with_info fehlgeschlagen: {exc}")
            return []

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.2,
        **kwargs: object,
    ) -> str:
        try:
            return self._chat_via_client(model, messages, temperature)
        except ImportError:
            return self._chat_via_http(model, messages, temperature)

    def _chat_via_client(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
    ) -> str:
        import ollama  # type: ignore[import]

        client = ollama.Client(host=self._base_url, timeout=self._timeout)
        response = client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )
        if isinstance(response, dict):
            return response["message"]["content"]
        return response.message.content or ""

    def _chat_via_http(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": False,
        }
        resp = requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
