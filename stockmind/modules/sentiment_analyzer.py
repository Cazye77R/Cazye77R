"""
StockMind – Sentiment-Analyse via LLM

Holt aktuelle News-Headlines von yfinance und bewertet sie mit dem
konfigurierten LLM-Provider auf einer Skala von -1 (sehr negativ)
bis +1 (sehr positiv). Das Ergebnis fließt als Feature in den
GradientBoostingClassifier und wird im UI angezeigt.

Das LLM liefert hier NUR Sentiment – keine Trade-Entscheidungen.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from modules.logger import logger  # noqa: E402

_SYSTEM_PROMPT = (
    "Du bist ein Finanzanalyse-Assistent. "
    "Antworte ausschließlich mit Zahlen, niemals mit Text."
)

_BATCH_SYSTEM_PROMPT = (
    "Du bist ein Finanzanalyse-Assistent. "
    "Antworte ausschließlich mit einer kommagetrennten Liste von Zahlen, "
    "niemals mit Text oder Erklärungen."
)


def analyze_news(
    ticker: str,
    n: int = 5,
    provider=None,
    model_name: str = "",
) -> dict:
    """
    Bewertet die neuesten News-Headlines für ``ticker`` mit dem LLM.

    Jede Headline erhält einen Sentiment-Score auf der Skala -1 … +1.
    Die Bewertung läuft als einziger Batch-Call (ein LLM-Aufruf für alle
    Headlines), um Latenz zu minimieren.

    Args:
        ticker:     Aktien-Symbol (z.B. "AAPL", "BMW.DE").
        n:          Maximale Anzahl auszuwertender Headlines.
        provider:   LLMProvider-Instanz; None → get_provider() nutzen.
        model_name: LLM-Modellname; leer → erstes verfügbares Modell.

    Returns:
        dict mit:
          score    – aggregierter Sentiment-Score [-1, +1]
          n_news   – Anzahl tatsächlich bewerteter Headlines
          samples  – list[dict] mit {"title": str, "score": float | None}
          error    – Fehlermeldung oder leer
    """
    headlines = _fetch_headlines(ticker, n)
    if not headlines:
        return {"score": 0.0, "n_news": 0, "samples": [], "error": "Keine Headlines gefunden."}

    if provider is None:
        from modules.llm_providers import get_provider
        provider = get_provider()

    if not model_name:
        try:
            models = provider.list_models()
            model_name = models[0] if models else ""
        except Exception:
            model_name = ""

    try:
        scores = _score_batch(headlines, ticker, provider, model_name)
    except Exception as exc:
        logger.warning(f"Sentiment-Batch fehlgeschlagen für {ticker}: {exc}")
        return {
            "score": 0.0,
            "n_news": len(headlines),
            "samples": [{"title": h, "score": None} for h in headlines],
            "error": str(exc),
        }

    valid = [s for s in scores if s is not None]
    agg = float(np.mean(valid)) if valid else 0.0

    return {
        "score": round(max(-1.0, min(1.0, agg)), 3),
        "n_news": len(headlines),
        "samples": [
            {"title": h, "score": s}
            for h, s in zip(headlines, scores)
        ],
        "error": "",
    }


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen
# ---------------------------------------------------------------------------

def _fetch_headlines(ticker: str, n: int) -> list[str]:
    """Holt bis zu ``n`` aktuelle Schlagzeilen via yfinance."""
    try:
        import yfinance as yf
        news_items = yf.Ticker(ticker).news or []
    except Exception as exc:
        logger.warning(f"yfinance News für {ticker} nicht abrufbar: {exc}")
        return []

    titles: list[str] = []
    for item in news_items:
        # Newer yfinance format: item["content"]["title"]
        # Older format:          item["title"]
        title = (
            (item.get("content") or {}).get("title")
            or item.get("title")
            or ""
        )
        title = title.strip()
        if title:
            titles.append(title)
        if len(titles) >= n:
            break
    return titles


def _score_batch(
    headlines: list[str],
    ticker: str,
    provider,
    model_name: str,
) -> list[Optional[float]]:
    """
    Sendet alle Headlines in einem LLM-Call und gibt eine Score-Liste zurück.

    Prompt-Format (entspricht der Aufgabenspezifikation, batch-optimiert):
      Bewerte folgende {n} Headline(s) für den Aktienkurs von {ticker} auf einer
      Skala von -1 (sehr negativ) bis +1 (sehr positiv).
      Antworte NUR mit {n} kommagetrennten Zahlen, eine pro Headline.
      Headline: {title}       ← (wenn n=1, Singular-Variante)
    """
    n = len(headlines)
    if n == 1:
        prompt = (
            f"Bewerte folgende Headline für den Aktienkurs von {ticker} auf einer "
            f"Skala von -1 (sehr negativ) bis +1 (sehr positiv). "
            f"Antworte NUR mit einer Zahl. "
            f"Headline: {headlines[0]}"
        )
    else:
        numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
        prompt = (
            f"Bewerte die folgenden {n} Headlines für den Aktienkurs von {ticker} "
            f"auf einer Skala von -1 (sehr negativ) bis +1 (sehr positiv). "
            f"Antworte NUR mit {n} kommagetrennten Zahlen (eine pro Headline, "
            f"in der gleichen Reihenfolge). Kein anderer Text.\n\n"
            f"Headlines:\n{numbered}"
        )

    system = _SYSTEM_PROMPT if n == 1 else _BATCH_SYSTEM_PROMPT
    response = provider.query(
        model=model_name,
        prompt=prompt,
        system_prompt=system,
        temperature=0.0,
    )
    return _parse_response(response, n)


def _parse_response(text: str, expected: int) -> list[Optional[float]]:
    """
    Extrahiert bis zu ``expected`` Float-Werte aus der LLM-Antwort.

    Akzeptiert: "0.3", "-0.7, 0.2, 0.8", "Scores: 0.3, -0.2", usw.
    Fehlende Werte werden mit None aufgefüllt.
    """
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    scores: list[Optional[float]] = []
    for raw in numbers[:expected]:
        try:
            val = float(raw)
            scores.append(max(-1.0, min(1.0, val)))
        except ValueError:
            scores.append(None)
    # Fehlende Stellen auffüllen
    while len(scores) < expected:
        scores.append(None)
    return scores
