import datetime
import logging
import re
from typing import Optional

import chromadb
import requests

from elephant.config import settings
from elephant.memory.extractor import MemoryExtractor
from elephant.memory.markdown_store import list_memories, save_memory
from elephant.memory.vector_store import embed_memory, search_similar
from elephant.utils.retry import OllamaError, ollama_retry

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """\
Du bist ein persönlicher Assistent mit Langzeitgedächtnis. \
Du erinnerst dich an folgende relevante Informationen:

[MEMORY START]
{memories}
[MEMORY END]

Nutze diese Erinnerungen wenn relevant, aber erzwinge es nicht.
Antworte ausführlich und detailliert auf Deutsch."""

NO_CONTEXT_PROMPT = (
    "Du bist ein persönlicher Assistent mit Langzeitgedächtnis. "
    "Aktuell liegen keine relevanten Erinnerungen für diese Anfrage vor. "
    "Antworte ausführlich und detailliert auf Deutsch."
)

_TITLE_CLEAN_RE = re.compile(r"[^\w\s-]")


class ChatEngine:
    def __init__(
        self,
        model: str = "llama3.1",
        collection: Optional[chromadb.Collection] = None,
        extractor: Optional[MemoryExtractor] = None,
    ):
        self.model = model
        self.collection = collection
        self.extractor = extractor if extractor is not None else MemoryExtractor(model=model)

    def _build_system_prompt(self, chunks: list[dict]) -> str:
        if not chunks:
            return NO_CONTEXT_PROMPT
        memories = "\n---\n".join(chunk["chunk"] for chunk in chunks)
        return SYSTEM_TEMPLATE.format(memories=memories)

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> tuple[str, list[dict]]:
        """Search memories, build RAG context, call Ollama.

        Returns (response_text, sources).
        """
        if conversation_history is None:
            conversation_history = []

        # 1. Semantic search in vector store
        sources = search_similar(user_message, top_k=5, collection=self.collection)

        # 2. Build system prompt with memory context
        system_prompt = self._build_system_prompt(sources)

        # 3. Compose full message list: system + history + new user message
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # 4. Ollama /api/chat call
        _model = model or self.model
        _messages = messages
        try:
            resp = ollama_retry(
                lambda m=_model, ms=_messages: requests.post(
                    f"{settings.ollama_url.rstrip('/')}/api/chat",
                    json={"model": m, "messages": ms, "stream": False},
                    timeout=120,
                ),
                label="chat",
            )
        except OllamaError:
            raise  # Propagate — main.py returns 503
        resp.raise_for_status()
        return resp.json()["message"]["content"], sources

    def extract_and_save(self, conversation: list[dict]) -> int:
        """Extract new facts from *conversation*, deduplicate, persist, and embed.

        Returns the number of memories actually saved.
        """
        if not conversation:
            return 0

        facts = self.extractor.extract_facts(conversation)
        if not facts:
            return 0

        existing = list_memories()
        unique = self.extractor.deduplicate(facts, existing, collection=self.collection)

        saved = 0
        for fact in unique:
            ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            clean = _TITLE_CLEAN_RE.sub("", fact.fact[:45]).strip()
            title = f"{clean}_{ts}" if clean else f"fact_{ts}"

            path = save_memory(
                category=fact.category,
                title=title,
                content=fact.fact,
                tags=fact.tags,
                importance=fact.importance,
            )
            embed_memory(path, collection=self.collection)

            logger.info(
                "[%s] Memory saved — category=%s importance=%.2f fact='%.70s'",
                datetime.datetime.utcnow().isoformat(),
                fact.category,
                fact.importance,
                fact.fact,
            )
            saved += 1

        return saved
