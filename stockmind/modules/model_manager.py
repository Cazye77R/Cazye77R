"""
StockMind – LLM Modell-Verwaltung (Provider-agnostisch)

Alle LLM-Calls werden durch den konfigurierten Provider geleitet.
Bestehende Funktions-Schnittstellen bleiben als Shims erhalten.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Generator

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, OLLAMA_TIMEOUT_S

from modules.llm_providers import get_provider
from modules.logger import logger

logger.debug(f"Module loaded: {__name__}")


# ANSI-Escape-Sequenzen aus subprocess-Output entfernen
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\r')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# 1. Verbindungscheck
# ---------------------------------------------------------------------------

def is_ollama_running() -> bool:
    """Prüft ob Ollama erreichbar ist. Shim für Rückwärtskompatibilität."""
    from modules.llm_providers.ollama_provider import OllamaProvider
    return OllamaProvider().health()


def is_llm_ready() -> bool:
    """Prüft ob der konfigurierte LLM-Provider bereit ist."""
    return get_provider().health()


def get_ollama_status() -> dict:
    """Status des Ollama-Providers. Shim für Rückwärtskompatibilität."""
    from modules.llm_providers.ollama_provider import OllamaProvider
    return OllamaProvider().get_status()


def get_llm_status() -> dict:
    """Status des konfigurierten Providers (provider-agnostisch)."""
    return get_provider().get_status()


# ---------------------------------------------------------------------------
# 2. Installierte Modelle abfragen
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    """Verfügbare Modelle des aktuellen Providers."""
    return get_provider().list_models()


def get_available_models_with_info() -> list[dict]:
    """Modell-Infos des aktuellen Providers (name, size_gb, modified, description)."""
    return get_provider().list_models_with_info()


def is_model_available(model: str) -> bool:
    """Prüft ob ein Modell beim aktuellen Provider verfügbar ist."""
    return model in get_available_models()


# ---------------------------------------------------------------------------
# 3. Modell herunterladen (Ollama-spezifisch)
# ---------------------------------------------------------------------------

def download_model(model_name: str) -> Generator[str, None, None]:
    """
    Lädt ein Ollama-Modell via `ollama pull` herunter und streamt den
    Fortschritt als einzelne Strings (geeignet für Streamlit st.empty()).

    Yields:
        Fortschritts-Strings wie "pulling manifest", "✅ llama3 erfolgreich heruntergeladen"

    Raises:
        RuntimeError: wenn `ollama` CLI nicht im PATH ist
        ConnectionError: wenn Ollama-Dienst nicht läuft
    """
    from modules.llm_providers.ollama_provider import OllamaProvider
    if not OllamaProvider().health():
        raise ConnectionError(
            f"Ollama-Dienst nicht erreichbar ({OLLAMA_BASE_URL}).\n"
            "Bitte starte Ollama mit `ollama serve` und versuche es erneut."
        )

    try:
        proc = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ollama CLI nicht gefunden. "
            "Bitte Ollama installieren: https://ollama.ai"
        )

    assert proc.stdout is not None
    last_line = ""
    for raw_line in proc.stdout:
        line = _strip_ansi(raw_line)
        if line and line != last_line:
            last_line = line
            logger.info(f"ollama pull {model_name}: {line.strip()}")
            yield line

    proc.wait()

    if proc.returncode == 0:
        yield f"✅ {model_name} erfolgreich heruntergeladen"
    else:
        yield f"⚠️ ollama pull beendet mit Fehlercode {proc.returncode}"


# ---------------------------------------------------------------------------
# 4. Inferenz
# ---------------------------------------------------------------------------

def query_model(
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_retries: int = 2,
) -> str:
    """
    Sendet eine Prompt-Anfrage an den konfigurierten LLM-Provider.

    Args:
        model_name:    Modell-Name
        prompt:        Benutzer-Prompt
        system_prompt: Optionaler System-Prompt
        temperature:   Kreativität 0.0–1.0
        max_retries:   Anzahl Wiederholungsversuche nach Fehlern

    Returns:
        Modell-Antwort als String

    Raises:
        RuntimeError: nach Erschöpfung aller Versuche
    """
    provider = get_provider()
    last_exc: Exception = RuntimeError("Unbekannter Fehler")

    for attempt in range(max_retries + 1):
        try:
            return provider.query(model_name, prompt, system_prompt, temperature)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                f"query_model Versuch {attempt + 1}/{max_retries + 1} fehlgeschlagen: {exc}"
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"Anfrage an '{model_name}' nach {max_retries + 1} Versuchen fehlgeschlagen: "
        f"{last_exc}"
    )


def chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """
    Niedrig-Level Chat-Schnittstelle.
    Stream-Modus wird nur bei Ollama unterstützt.
    """
    if stream:
        # Streaming direkt über Ollama HTTP-API
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": True,
        }
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT_S,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Ollama nicht erreichbar ({OLLAMA_BASE_URL}). Bitte `ollama serve` starten."
            )

        def _token_gen() -> Generator[str, None, None]:
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield delta
        return _token_gen()

    return get_provider().chat(messages, model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# 5. Aktienanalyse-Prompt
# ---------------------------------------------------------------------------

_ANALYST_SYSTEM_PROMPT = (
    "Du bist StockMind, ein erfahrener KI-Finanzanalyst. "
    "Du analysierst Aktien anhand technischer Indikatoren und gibst klare, "
    "strukturierte Handlungsempfehlungen (Kaufen / Halten / Verkaufen) mit Begründung. "
    "Weise stets darauf hin, dass dies keine Anlageberatung ist. "
    "Antworte auf Deutsch."
)


def analyze_stock(
    model: str,
    ticker: str,
    context: str,
    method: str = "Auto (KI wählt)",
) -> str:
    """Erstellt eine strukturierte Aktienanalyse mit dem LLM."""
    user_prompt = (
        f"Analysiere die Aktie **{ticker}** mit der Methode **{method}**.\n\n"
        f"Aktuelle Marktdaten und Indikatoren:\n{context}\n\n"
        "Gib eine strukturierte Analyse mit:\n"
        "1. Kurzzusammenfassung der Marktlage\n"
        "2. Signale aus den Indikatoren\n"
        "3. Handlungsempfehlung (Kaufen / Halten / Verkaufen)\n"
        "4. Risiken und Hinweis: Dies ist keine Anlageberatung."
    )
    return query_model(
        model_name=model,
        prompt=user_prompt,
        system_prompt=_ANALYST_SYSTEM_PROMPT,
        temperature=0.2,
    )


# ---------------------------------------------------------------------------
# Backward-Kompatibilität (alte Funktionsnamen bleiben erhalten)
# ---------------------------------------------------------------------------

def list_local_models() -> list[str]:
    """Alias für get_available_models()."""
    return get_available_models()


def pull_model(model: str) -> Generator[str, None, None]:
    """Alias für download_model()."""
    return download_model(model)


def ensure_model(model: str) -> tuple[bool, str]:
    """Prüft ob ein Modell verfügbar ist. Returns (True, '') oder (False, Fehlermeldung)."""
    if is_model_available(model):
        return True, ""
    return (
        False,
        f"Modell '{model}' ist nicht lokal installiert. "
        "Bitte über die Sidebar herunterladen.",
    )
