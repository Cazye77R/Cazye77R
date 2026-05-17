import json
import logging
import re
from typing import Literal, Optional

import requests
from pydantic import BaseModel, Field, ValidationError

from elephant.config import settings
from elephant.memory.vector_store import search_similar
from elephant.utils.retry import OllamaError, ollama_retry

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """\
Analysiere diese Konversation und extrahiere wichtige Fakten die es wert sind sich zu merken.
Ignoriere Smalltalk und triviale Aussagen.

Für jeden Fakt gib zurück:
- fact: Der Fakt als klarer Satz
- category: general | projects | conversations
- tags: relevante Tags als Liste
- importance: 0.0-1.0 (wie wichtig ist es sich daran zu erinnern?)

Antworte NUR als JSON Array. Keine Erklärung.

Konversation:
{transcript}"""

_STRICT_SUFFIX = (
    "\n\nWICHTIG: Antworte AUSSCHLIESSLICH mit einem validen JSON Array. "
    "Kein Text davor oder danach. Kein Markdown. Nur [...] mit den Objekten."
)


class MemoryFact(BaseModel):
    fact: str
    category: Literal["general", "projects", "conversations"]
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryExtractor:
    def __init__(self, model: str = "llama3.1"):
        self.model = model

    def _build_transcript(self, conversation: list[dict]) -> str:
        lines = []
        for msg in conversation:
            role = "User" if msg["role"] == "user" else "Assistent"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def extract_facts(self, conversation: list[dict]) -> list[MemoryFact]:
        """Call Ollama to extract structured facts from a conversation transcript."""
        if not conversation:
            return []

        transcript = self._build_transcript(conversation)
        base_prompt = EXTRACT_PROMPT.format(transcript=transcript)

        for attempt in range(1, 4):
            prompt = base_prompt if attempt == 1 else base_prompt + _STRICT_SUFFIX
            try:
                resp = ollama_retry(
                    lambda p=prompt: requests.post(
                        f"{settings.ollama_url.rstrip('/')}/api/chat",
                        json={"model": self.model,
                              "messages": [{"role": "user", "content": p}],
                              "stream": False},
                        timeout=120,
                    ),
                    label=f"extract_facts attempt {attempt}",
                )
                resp.raise_for_status()
            except OllamaError as exc:
                logger.error("Ollama unavailable during fact extraction: %s", exc)
                return []

            raw = resp.json()["message"]["content"]
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                logger.warning("Attempt %d/3: no JSON array in LLM response", attempt)
                continue

            try:
                data = json.loads(match.group())
            except json.JSONDecodeError as exc:
                logger.warning("Attempt %d/3: JSON parse failed: %s", attempt, exc)
                continue

            facts: list[MemoryFact] = []
            for item in data:
                try:
                    facts.append(MemoryFact(**item))
                except (ValidationError, TypeError) as exc:
                    logger.warning("Skipping invalid fact item: %s", exc)
            return facts

        logger.error("All 3 extraction attempts failed — returning empty")
        return []

    def deduplicate(
        self,
        new_facts: list[MemoryFact],
        existing_memories: list,
        collection=None,
        similarity_threshold: float = 0.85,
    ) -> list[MemoryFact]:
        """Remove facts already present in ChromaDB (cosine score >= threshold)."""
        if not new_facts or not existing_memories or collection is None:
            return new_facts

        unique: list[MemoryFact] = []
        for fact in new_facts:
            results = search_similar(fact.fact, top_k=1, collection=collection)
            if results and results[0]["score"] >= similarity_threshold:
                logger.debug(
                    "Deduplicating fact (score=%.3f): %.60s",
                    results[0]["score"],
                    fact.fact,
                )
            else:
                unique.append(fact)
        return unique
