"""Ollama-Modell-Konstanten (lädt OLLAMA_HOST aus der Umgebung)."""

from __future__ import annotations

import os

# --- Ollama API ---
# Überschreibbar per OLLAMA_HOST=http://my-server:11434 in .env
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT_S: int = 120

# --- Modelle ---
DEFAULT_MODEL: str = "llama3"

AVAILABLE_MODELS: list[str] = [
    "llama3",
    "mistral",
    "phi3",
    "gemma2",
    "qwen2",
]

MODEL_DESCRIPTIONS: dict[str, str] = {
    "llama3":  "Ausgewogen, gut für Analyse",
    "mistral": "Schnell, effizient",
    "phi3":    "Klein & sparsam",
    "gemma2":  "Googles Modell",
    "qwen2":   "Mehrsprachig",
}
