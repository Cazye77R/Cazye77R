"""HTTP client for the Ollama local LLM API."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Generator

from core.config import CHAT_MODEL, EMBED_MODEL, OLLAMA_URL


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable or returns an unexpected response."""


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Ollama nicht erreichbar unter {self.base_url}. "
                f"Starte Ollama mit 'ollama serve'. Details: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaConnectionError(f"Ungültige Antwort von Ollama: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as resp:
                data = json.loads(resp.read())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def get_embedding(self, text: str) -> list[float]:
        result = self._request(
            "/api/embeddings", {"model": EMBED_MODEL, "prompt": text}, timeout=60
        )
        embedding = result.get("embedding", [])
        if not embedding:
            raise OllamaConnectionError(
                f"Ollama lieferte kein Embedding. Ist das Modell '{EMBED_MODEL}' geladen? "
                f"Führe 'ollama pull {EMBED_MODEL}' aus."
            )
        return embedding

    def chat(self, messages: list[dict[str, str]], system_prompt: str = "") -> str:
        full_messages = (
            [{"role": "system", "content": system_prompt}] + messages
            if system_prompt
            else messages
        )
        result = self._request(
            "/api/chat",
            {"model": CHAT_MODEL, "messages": full_messages, "stream": False},
            timeout=180,
        )
        return result.get("message", {}).get("content", "")

    def chat_stream(
        self, messages: list[dict[str, str]], system_prompt: str = ""
    ) -> Generator[str, None, None]:
        full_messages = (
            [{"role": "system", "content": system_prompt}] + messages
            if system_prompt
            else messages
        )
        url = f"{self.base_url}/api/chat"
        data = json.dumps({"model": CHAT_MODEL, "messages": full_messages, "stream": True}).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Ollama-Stream unterbrochen: {exc}"
            ) from exc
