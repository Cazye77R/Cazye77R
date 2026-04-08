"""RAG-based chat: retrieve relevant chunks, stream an LLM answer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, List, Tuple

try:
    from .searcher import SearchIndex, SearchResult, search
except ImportError:
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from text_search.searcher import SearchIndex, SearchResult, search  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama": "llama3.2:1b",
    "claude": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
}

# Small models recommended for local use — ordered by size ascending
MODEL_CATALOG: dict[str, dict] = {
    "qwen2.5:0.5b": {"size_gb": 0.4, "label": "Ultra-kompakt (~400 MB) — sehr schnell"},
    "llama3.2:1b":  {"size_gb": 1.3, "label": "Klein & schnell (~1,3 GB) — empfohlen"},
    "llama3.2:3b":  {"size_gb": 2.0, "label": "Ausgewogen (~2,0 GB) — gute Qualität"},
    "phi3-mini":    {"size_gb": 2.2, "label": "Phi-3 Mini (~2,2 GB) — Microsoft"},
}
DEFAULT_SMALL_MODEL = "llama3.2:1b"


@dataclass
class OllamaStatus:
    installed: bool          # ollama binary found on PATH
    running: bool            # /api/tags reachable
    model_ready: bool        # requested model already pulled
    available_models: list   # all pulled model names


def check_ollama_status(host: str, model: str) -> OllamaStatus:
    """Fast check of Ollama availability and whether *model* is pulled."""
    import shutil
    installed = shutil.which("ollama") is not None
    if not installed:
        return OllamaStatus(installed=False, running=False, model_ready=False, available_models=[])
    try:
        import requests as _req
        resp = _req.get(f"{host}/api/tags", timeout=3)
        resp.raise_for_status()
        raw_models = [m["name"] for m in resp.json().get("models", [])]
        # Accept "llama3.2:1b", "llama3.2:1b:latest" or bare name matching ":latest" suffix
        def _matches(name: str, target: str) -> bool:
            if name == target:
                return True
            if name == f"{target}:latest":
                return True
            if target.endswith(":latest") and name == target[:-7]:
                return True
            return False
        ready = any(_matches(m, model) for m in raw_models)
        return OllamaStatus(installed=True, running=True, model_ready=ready, available_models=raw_models)
    except Exception:
        return OllamaStatus(installed=True, running=False, model_ready=False, available_models=[])


@dataclass
class ChatConfig:
    provider: str = "ollama"          # "ollama" | "claude" | "openai"
    model: str = DEFAULT_SMALL_MODEL
    api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    context_chunks: int = 3           # fewer = faster
    temperature: float = 0.2


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def answer_question(
    question: str,
    search_index: SearchIndex,
    config: ChatConfig,
) -> Tuple[Generator[str, None, None], List[SearchResult]]:
    """Retrieve top chunks, build a RAG prompt, stream the answer.

    Returns (token_generator, source_results) so the caller can
    stream with st.write_stream() and show sources separately.
    """
    sources = search(
        search_index,
        query=question,
        mode="hybrid" if search_index.embedding_index is not None else "keyword",
        top_k=config.context_chunks,
    )
    prompt = _build_prompt(question, sources)
    generator = _stream(prompt, config)
    return generator, sources


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _build_prompt(question: str, sources: List[SearchResult]) -> str:
    context_parts: list[str] = []
    for i, r in enumerate(sources, 1):
        loc = ""
        if r.chunk.page is not None:
            loc = f", Seite {r.chunk.page}"
        elif r.chunk.line_start is not None:
            loc = f", Zeile {r.chunk.line_start}"
        context_parts.append(
            f"[{i}] [Quelle: {r.chunk.source}{loc}, Chunk #{r.chunk.chunk_id}]\n{r.chunk.text}"
        )
    context_block = "\n\n".join(context_parts)

    system = (
        "Du bist ein präziser Assistent. Beantworte die Frage ausschließlich auf "
        "Basis der unten aufgeführten Textausschnitte. "
        "Zitiere jeden verwendeten Textausschnitt mit seiner Nummer in eckigen Klammern, "
        "z. B. [1] oder [2], direkt im Antworttext. "
        "Falls die Antwort nicht hervorgeht, antworte: "
        "\"Die Dokumente enthalten keine Information dazu.\"\n"
        "WICHTIG: Verwende ausschließlich die bereitgestellten Textausschnitte. "
        "Kein externes Wissen, keine eigenen Schlussfolgerungen über den Dokumentinhalt hinaus.\n"
        "Antworte auf Deutsch."
    )
    return f"SYSTEM:\n{system}\n\nKONTEXT:\n{context_block}\n\nUSER:\n{question}"


def _split_prompt(prompt: str) -> Tuple[str, str]:
    """Split the combined prompt string into (system_msg, user_msg)."""
    parts = prompt.split("\n\nUSER:\n", 1)
    system_and_context = parts[0]
    user_msg = parts[1] if len(parts) > 1 else ""
    # Extract system text (after "SYSTEM:\n")
    system_msg = system_and_context.removeprefix("SYSTEM:\n")
    return system_msg, user_msg


# ---------------------------------------------------------------------------
# Streaming dispatch
# ---------------------------------------------------------------------------

def _stream(prompt: str, config: ChatConfig) -> Generator[str, None, None]:
    if config.provider == "ollama":
        yield from _stream_ollama(prompt, config)
    elif config.provider == "claude":
        yield from _stream_claude(prompt, config)
    elif config.provider == "openai":
        yield from _stream_openai(prompt, config)
    else:
        raise ValueError(f"Unbekannter Provider: {config.provider}")


def _stream_ollama(prompt: str, config: ChatConfig) -> Generator[str, None, None]:
    import json
    try:
        import requests
    except ImportError as exc:
        raise ImportError("requests ist nicht installiert.") from exc

    system_msg, user_msg = _split_prompt(prompt)
    payload = {
        "model": config.model,
        "system": system_msg,
        "prompt": user_msg,
        "stream": True,
        "options": {"temperature": config.temperature},
    }
    try:
        resp = requests.post(
            f"{config.ollama_host}/api/generate",
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Ollama läuft nicht. Bitte Ollama starten (ollama serve) und das gewünschte "
            f"Modell laden (ollama pull {config.model})."
        )
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise RuntimeError(
                f"Das Modell '{config.model}' ist in Ollama nicht installiert.\n"
                f"Bitte installieren mit:  ollama pull {config.model}"
            )
        raise

    for line in resp.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        token = data.get("response", "")
        if token:
            yield token
        if data.get("done"):
            break


def _stream_claude(prompt: str, config: ChatConfig) -> Generator[str, None, None]:
    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Das anthropic-Paket ist nicht installiert. Bitte installieren: pip install anthropic"
        ) from exc

    system_msg, user_msg = _split_prompt(prompt)
    client = anthropic.Anthropic(api_key=config.api_key)
    with client.messages.stream(
        model=config.model,
        max_tokens=1024,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}],
        temperature=config.temperature,
    ) as stream:
        yield from stream.text_stream


def _stream_openai(prompt: str, config: ChatConfig) -> Generator[str, None, None]:
    try:
        import openai as _openai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Das openai-Paket ist nicht installiert. Bitte installieren: pip install openai"
        ) from exc

    system_msg, user_msg = _split_prompt(prompt)
    client = _openai.OpenAI(api_key=config.api_key)
    stream = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=config.temperature,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content
