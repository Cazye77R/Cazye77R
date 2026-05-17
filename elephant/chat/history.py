from typing import Optional

import requests

from elephant.config import settings
from elephant.utils.retry import OllamaError, ollama_retry


class ConversationHistory:
    """Sliding-window conversation buffer for a single chat session.

    Each "turn" is one user message + one assistant reply (2 messages).
    When max_turns is exceeded, the oldest turn is evicted.
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._messages: list[dict] = []

    def add(self, role: str, content: str) -> None:
        """Append a message and evict the oldest turn if over the limit."""
        self._messages.append({"role": role, "content": content})
        max_msgs = self.max_turns * 2
        if len(self._messages) > max_msgs:
            self._messages = self._messages[2:]

    def messages(self) -> list[dict]:
        """Return a snapshot of all stored messages."""
        return list(self._messages)

    def turn_count(self) -> int:
        return len(self._messages) // 2

    @classmethod
    def from_messages(cls, messages: list[dict], max_turns: int = 20) -> "ConversationHistory":
        """Create a ConversationHistory pre-loaded with an existing message list."""
        instance = cls(max_turns=max_turns)
        instance._messages = list(messages)
        return instance

    def export_summary(
        self,
        model: Optional[str] = None,
        ollama_url: Optional[str] = None,
    ) -> str:
        """Summarise the conversation in 3–5 sentences via Ollama."""
        if not self._messages:
            return "Keine Konversation vorhanden."

        model = model or settings.ollama_model
        url = (ollama_url or settings.ollama_url).rstrip("/")

        transcript = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistent'}: {m['content']}"
            for m in self._messages
        )
        prompt = (
            "Fasse die folgende Konversation in 3–5 prägnanten Sätzen auf Deutsch zusammen:\n\n"
            + transcript
        )

        try:
            resp = ollama_retry(
                lambda: requests.post(
                    f"{url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                    timeout=120,
                ),
                label="export_summary",
            )
        except OllamaError:
            return "Ollama nicht erreichbar — Zusammenfassung konnte nicht erstellt werden."
        resp.raise_for_status()
        return resp.json()["message"]["content"]
