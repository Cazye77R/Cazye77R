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
    "ollama": "llama3.2",
    "claude": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
}


@dataclass
class ChatConfig:
    provider: str = "ollama"          # "ollama" | "claude" | "openai"
    model: str = "llama3.2"
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
    for r in sources:
        loc = ""
        if r.chunk.page is not None:
            loc = f", Seite {r.chunk.page}"
        elif r.chunk.line_start is not None:
            loc = f", Zeile {r.chunk.line_start}"
        context_parts.append(
            f"[Quelle: {r.chunk.source}{loc}, Chunk #{r.chunk.chunk_id}]\n{r.chunk.text}"
        )
    context_block = "\n\n".join(context_parts)

    system = (
        "Du bist ein präziser Assistent. Beantworte die Frage ausschließlich auf "
        "Basis der unten aufgeführten Textausschnitte. Falls die Antwort nicht "
        "hervorgeht, antworte: \"Die Dokumente enthalten keine Information dazu.\"\n"
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
