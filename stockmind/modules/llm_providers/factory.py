"""StockMind – LLM Provider Factory."""
from __future__ import annotations

import os

from modules.llm_providers.base import LLMProvider
from modules.llm_providers.nvidia_provider import NvidiaProvider
from modules.llm_providers.ollama_provider import OllamaProvider


def get_provider(name: str | None = None) -> LLMProvider:
    """
    Gibt den konfigurierten LLM-Provider zurück.

    Args:
        name: Provider-Name ("ollama" | "nvidia"). Liest LLM_PROVIDER aus
              os.environ wenn None. Standard: "ollama".

    Returns:
        Instanz von OllamaProvider oder NvidiaProvider.
    """
    n = (name or os.getenv("LLM_PROVIDER", "ollama")).lower()
    if n == "nvidia":
        return NvidiaProvider()
    return OllamaProvider()
