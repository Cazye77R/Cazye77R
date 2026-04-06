"""
StockMind – Ollama Modell-Verwaltung
Prüft verfügbare Modelle, löst Auto-Download aus und stellt eine einheitliche
Chat-Schnittstelle bereit.
"""

from __future__ import annotations

import json
from typing import Generator, Optional

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import AVAILABLE_MODELS, DEFAULT_MODEL, OLLAMA_BASE_URL, OLLAMA_TIMEOUT_S


# ---------------------------------------------------------------------------
# Modell-Verwaltung
# ---------------------------------------------------------------------------

def list_local_models() -> list[str]:
    """
    Gibt alle lokal bei Ollama installierten Modell-Namen zurück.
    Gibt leere Liste zurück wenn Ollama nicht erreichbar ist.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"].split(":")[0] for m in resp.json().get("models", [])]
    except Exception:
        return []


def is_model_available(model: str) -> bool:
    """Prüft ob ein Modell lokal installiert ist."""
    return model in list_local_models()


def pull_model(model: str) -> Generator[str, None, None]:
    """
    Startet den Download eines Ollama-Modells und liefert Fortschritts-Strings
    via Generator (für Streamlit st.status / st.write).

    Raises:
        ConnectionError: wenn Ollama nicht läuft
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model, "stream": True},
            stream=True,
            timeout=OLLAMA_TIMEOUT_S,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                status = data.get("status", "")
                total = data.get("total", 0)
                completed = data.get("completed", 0)
                if total:
                    pct = int(completed / total * 100)
                    yield f"{status} – {pct}%"
                else:
                    yield status
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Ollama ist nicht erreichbar unter {OLLAMA_BASE_URL}. "
            "Bitte starte Ollama (`ollama serve`) und versuche es erneut."
        )


def ensure_model(model: str) -> tuple[bool, str]:
    """
    Stellt sicher, dass ein Modell lokal vorhanden ist.
    Gibt (True, '') oder (False, Fehlermeldung) zurück.
    Für den Auto-Download in der UI wird pull_model() direkt verwendet.
    """
    if is_model_available(model):
        return True, ""
    return False, f"Modell '{model}' ist nicht lokal installiert. Bitte über die Sidebar herunterladen."


# ---------------------------------------------------------------------------
# Inferenz
# ---------------------------------------------------------------------------

def chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """
    Sendet eine Chat-Anfrage an Ollama.

    Args:
        model:       Modell-Name (z.B. 'llama3')
        messages:    Liste von {'role': 'user'|'assistant'|'system', 'content': '...'}
        temperature: Kreativität (0 = deterministisch)
        stream:      True → Generator über Teil-Tokens

    Returns:
        Vollständige Antwort (str) oder Token-Generator bei stream=True

    Raises:
        ConnectionError: Ollama nicht erreichbar
        ValueError:      Unbekannter Fehler in der Antwort
    """
    payload = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature},
        "stream": stream,
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            stream=stream,
            timeout=OLLAMA_TIMEOUT_S,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Ollama nicht erreichbar ({OLLAMA_BASE_URL}). Bitte `ollama serve` starten."
        )

    if stream:
        def _token_gen() -> Generator[str, None, None]:
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield delta
        return _token_gen()
    else:
        return resp.json()["message"]["content"]


def analyze_stock(
    model: str,
    ticker: str,
    context: str,
    method: str = "Auto (KI wählt)",
) -> str:
    """
    Erstellt eine Aktienanalyse mit dem LLM.

    Args:
        model:   Ollama-Modellname
        ticker:  Aktien-Ticker
        context: Technische Indikatoren / Kursdaten als Textzusammenfassung
        method:  Gewählte Analysemethode

    Returns:
        Analyse-Text des Modells
    """
    system_prompt = (
        "Du bist StockMind, ein erfahrener KI-Finanzanalyst. "
        "Du analysierst Aktien anhand technischer Indikatoren und gibst klare, "
        "strukturierte Handlungsempfehlungen (Kaufen / Halten / Verkaufen) mit Begründung. "
        "Weise stets darauf hin, dass dies keine Anlageberatung ist. "
        "Antworte auf Deutsch."
    )
    user_prompt = (
        f"Analysiere die Aktie **{ticker}** mit der Methode **{method}**.\n\n"
        f"Aktuelle Marktdaten und Indikatoren:\n{context}\n\n"
        "Gib eine strukturierte Analyse mit:\n"
        "1. Kurzzusammenfassung der Marktlage\n"
        "2. Signale aus den Indikatoren\n"
        "3. Handlungsempfehlung (Kaufen / Halten / Verkaufen)\n"
        "4. Risiken und Hinweis: Dies ist keine Anlageberatung."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return chat(model, messages, temperature=0.2)
