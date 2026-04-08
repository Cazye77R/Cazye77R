"""
StockMind – Ollama Modell-Verwaltung
Modell-Erkennung, Download via subprocess, Verbindungscheck und
Inferenz via ollama Python-Client mit Retry-Logik.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Generator, Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import AVAILABLE_MODELS, DEFAULT_MODEL, MODEL_DESCRIPTIONS, OLLAMA_BASE_URL, OLLAMA_TIMEOUT_S
from modules.logger import logger

logger.debug(f"Module loaded: {__name__}")


# ANSI-Escape-Sequenzen aus subprocess-Output entfernen
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\r')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# 1. Verbindungscheck
# ---------------------------------------------------------------------------

_INSTALL_GUIDE = """
**Ollama ist nicht erreichbar.**

Installation:
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# → https://ollama.ai/download/windows
```

Dienst starten:
```bash
ollama serve
```

Erstes Modell laden:
```bash
ollama pull llama3
```
""".strip()


def is_ollama_running() -> bool:
    """
    Prüft ob der Ollama-Dienst unter OLLAMA_BASE_URL erreichbar ist.

    Returns:
        True wenn Ollama antwortet, False sonst.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception as _exc:
        logger.debug(f"Ollama nicht erreichbar: {_exc}")
        return False


def get_ollama_status() -> dict:
    """
    Gibt erweiterten Verbindungsstatus zurück.

    Returns:
        {
          "running": bool,
          "url": str,
          "model_count": int,
          "error": str,          # leer wenn running=True
          "install_guide": str,  # leer wenn running=True
        }
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return {
            "running": True,
            "url": OLLAMA_BASE_URL,
            "model_count": len(models),
            "error": "",
            "install_guide": "",
        }
    except requests.exceptions.ConnectionError:
        return {
            "running": False,
            "url": OLLAMA_BASE_URL,
            "model_count": 0,
            "error": f"Verbindung zu {OLLAMA_BASE_URL} abgelehnt.",
            "install_guide": _INSTALL_GUIDE,
        }
    except requests.exceptions.Timeout:
        return {
            "running": False,
            "url": OLLAMA_BASE_URL,
            "model_count": 0,
            "error": f"Timeout beim Verbinden mit {OLLAMA_BASE_URL} (>3s).",
            "install_guide": _INSTALL_GUIDE,
        }
    except Exception as exc:
        return {
            "running": False,
            "url": OLLAMA_BASE_URL,
            "model_count": 0,
            "error": str(exc),
            "install_guide": _INSTALL_GUIDE,
        }


# ---------------------------------------------------------------------------
# 2. Installierte Modelle abfragen
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    """
    Fragt die lokale Ollama-Instanz nach installierten Modellen ab
    (GET /api/tags).

    Returns:
        Liste der Modell-Namen ohne Tag-Suffix, z.B. ["llama3", "mistral"].
        Leere Liste wenn Ollama nicht erreichbar ist.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        # "llama3:latest" → "llama3"
        return [m["name"].split(":")[0] for m in models]
    except Exception as _exc:
        logger.debug(f"get_available_models fehlgeschlagen: {_exc}")
        return []


def get_available_models_with_info() -> list[dict]:
    """
    Wie get_available_models(), aber mit Größe und Modifikationsdatum.

    Returns:
        [{"name": str, "size_gb": float, "modified": str, "description": str}]
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        result = []
        for m in models:
            name = m["name"].split(":")[0]
            size_bytes = m.get("size", 0)
            result.append({
                "name": name,
                "full_name": m["name"],
                "size_gb": round(size_bytes / 1024**3, 2) if size_bytes else 0.0,
                "modified": m.get("modified_at", "")[:10],
                "description": MODEL_DESCRIPTIONS.get(name, ""),
            })
        return result
    except Exception as _exc:
        logger.debug(f"get_available_models_with_info fehlgeschlagen: {_exc}")
        return []


def is_model_available(model: str) -> bool:
    """Prüft ob ein Modell lokal installiert ist."""
    return model in get_available_models()


# ---------------------------------------------------------------------------
# 3. Modell herunterladen (subprocess-Streaming)
# ---------------------------------------------------------------------------

def download_model(model_name: str) -> Generator[str, None, None]:
    """
    Lädt ein Ollama-Modell via `ollama pull` herunter und streamt den
    Fortschritt als einzelne Strings (geeignet für Streamlit st.empty()).

    Strategie: subprocess.Popen mit stdout=PIPE, ANSI-Codes werden gefiltert.
    Der Generator beendet sich wenn der Prozess fertig ist.

    Yields:
        Fortschritts-Strings wie "pulling manifest", "pulling a3…  45%",
        "✅ llama3 erfolgreich heruntergeladen" oder "⚠️ Fehler: …"

    Raises:
        RuntimeError: wenn `ollama` CLI nicht im PATH ist
        ConnectionError: wenn Ollama-Dienst nicht läuft
    """
    if not is_ollama_running():
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
# 4. Inferenz via ollama Python-Client (mit Retry)
# ---------------------------------------------------------------------------

def query_model(
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_retries: int = 2,
) -> str:
    """
    Sendet eine Prompt-Anfrage an das lokale Ollama-Modell via
    ollama Python-Client. Fällt automatisch auf HTTP-API zurück wenn
    das ollama-Package nicht installiert ist.

    Args:
        model_name:   Modell-Name (z.B. 'llama3')
        prompt:       Benutzer-Prompt
        system_prompt: Optionaler System-Prompt (Persona / Instruktionen)
        temperature:  Kreativität 0.0–1.0 (0 = deterministisch)
        max_retries:  Anzahl Wiederholungsversuche nach Fehlern (default: 2)

    Returns:
        Modell-Antwort als String

    Raises:
        RuntimeError: nach Erschöpfung aller Versuche
        ConnectionError: wenn Ollama nicht erreichbar ist
    """
    if not is_ollama_running():
        raise ConnectionError(
            f"Ollama nicht erreichbar ({OLLAMA_BASE_URL}). "
            "Bitte `ollama serve` starten."
        )

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_exc: Exception = RuntimeError("Unbekannter Fehler")

    for attempt in range(max_retries + 1):
        try:
            return _query_via_client(model_name, messages, temperature)
        except ImportError:
            # ollama package nicht installiert → HTTP-Fallback
            return _query_via_http(model_name, messages, temperature)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"query_model Versuch {attempt + 1}/{max_retries + 1} fehlgeschlagen: {exc}")
            if attempt < max_retries:
                wait = 2 ** attempt          # 1s, 2s
                time.sleep(wait)

    raise RuntimeError(
        f"Anfrage an '{model_name}' nach {max_retries + 1} Versuchen fehlgeschlagen: "
        f"{last_exc}"
    )


def _query_via_client(
    model_name: str,
    messages: list[dict],
    temperature: float,
) -> str:
    """Inferenz via ollama Python-Package."""
    import ollama  # type: ignore[import]

    client = ollama.Client(
        host=OLLAMA_BASE_URL,
        timeout=OLLAMA_TIMEOUT_S,
    )
    response = client.chat(
        model=model_name,
        messages=messages,
        options={"temperature": temperature},
    )
    # ollama-Client gibt entweder dict oder ChatResponse-Objekt zurück
    if isinstance(response, dict):
        return response["message"]["content"]
    return response.message.content


def _query_via_http(
    model_name: str,
    messages: list[dict],
    temperature: float,
) -> str:
    """Inferenz via direkter HTTP-Anfrage (Fallback ohne ollama-Package)."""
    payload = {
        "model": model_name,
        "messages": messages,
        "options": {"temperature": temperature},
        "stream": False,
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=OLLAMA_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


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
    """
    Erstellt eine strukturierte Aktienanalyse mit dem LLM.

    Args:
        model:   Ollama-Modellname
        ticker:  Aktien-Ticker
        context: Technische Indikatoren / Kursdaten als Textzusammenfassung
        method:  Gewählte Analysemethode

    Returns:
        Analyse-Text des Modells
    """
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
    """Alias für get_available_models() – Rückwärtskompatibilität."""
    return get_available_models()


def pull_model(model: str) -> Generator[str, None, None]:
    """Alias für download_model() – Rückwärtskompatibilität."""
    return download_model(model)


def ensure_model(model: str) -> tuple[bool, str]:
    """
    Prüft ob ein Modell verfügbar ist.
    Returns (True, '') oder (False, Fehlermeldung).
    """
    if is_model_available(model):
        return True, ""
    return (
        False,
        f"Modell '{model}' ist nicht lokal installiert. "
        "Bitte über die Sidebar herunterladen.",
    )


def chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """
    Niedrig-Level Chat-Schnittstelle (HTTP-API direkt).
    Für Streaming oder wenn messages manuell zusammengebaut werden.

    Für den Standardfall query_model() bevorzugen.
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

    return resp.json()["message"]["content"]
