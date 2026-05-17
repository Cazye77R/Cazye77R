from typing import Optional

import chromadb
import requests

from elephant.config import settings
from elephant.memory.vector_store import search_similar

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


class ChatEngine:
    def __init__(
        self,
        model: str = "llama3.1",
        collection: Optional[chromadb.Collection] = None,
    ):
        self.model = model
        self.collection = collection

    def _build_system_prompt(self, chunks: list[dict]) -> str:
        if not chunks:
            return NO_CONTEXT_PROMPT
        memories = "\n---\n".join(chunk["chunk"] for chunk in chunks)
        return SYSTEM_TEMPLATE.format(memories=memories)

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> tuple[str, list[dict]]:
        """Search memories, build RAG context, call Ollama.

        Returns (response_text, sources) where sources is the list of
        memory chunks used to build the context.
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
        resp = requests.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"], sources
