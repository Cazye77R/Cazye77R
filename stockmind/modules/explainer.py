"""
StockMind – ML-Entscheidungs-Erklärer

Übersetzt die Top-Features des trainierten GradientBoostingClassifiers und
den Sentiment-Score in einen verständlichen deutschen Erklärungstext.

Das LLM liefert hier NUR eine Erklärung – keine Trade-Entscheidung.
Trade-Entscheidungen laufen ausschließlich über ML-Score + Risk Manager.
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from modules.logger import logger  # noqa: E402

# Lesbare deutsche Bezeichnungen für Feature-Namen
_FEATURE_LABELS: dict[str, str] = {
    "ret_1d":         "1-Tages-Rendite",
    "ret_5d":         "5-Tages-Rendite",
    "ret_20d":        "20-Tages-Rendite",
    "sma_20":         "Abstand SMA-20",
    "sma_50":         "Abstand SMA-50",
    "sma_cross":      "SMA-20/50-Kreuzung",
    "volatility_20d": "20-Tages-Volatilität",
    "vol_ratio":      "Volumen-Ratio",
    "rsi":            "RSI (14)",
    "macd_hist":      "MACD-Histogramm",
    "bb_pos":         "Bollinger-Position",
    "hl_range":       "High-Low-Range",
    "sentiment":      "News-Sentiment",
}

_SYSTEM_PROMPT = (
    "Du bist StockMind, ein KI-Finanzassistent. "
    "Erkläre ML-Handelsentscheidungen klar und verständlich auf Deutsch "
    "für Privatanleger ohne Fachjargon. "
    "Antworte in maximal 3 Sätzen. "
    "Beginne direkt mit der Erklärung, ohne Präambel."
)


def explain_decision(
    features: dict[str, float],
    prediction: str,
    sentiment_score: float,
    feature_importances: dict[str, float],
    provider: Any = None,
    model_name: str = "",
) -> str:
    """
    Erstellt eine deutsche Klartext-Erklärung der ML-Entscheidung.

    Args:
        features:            Dict {feature_name: aktueller_wert} der letzten Zeile.
        prediction:          Signal-String ("KAUFEN" | "HALTEN" | "VERKAUFEN").
        sentiment_score:     Aggregierter Sentiment-Score aus analyze_news() [-1, +1].
        feature_importances: Dict {feature_name: importance} aus model.feature_importances_.
        provider:            LLMProvider-Instanz; None → get_provider() nutzen.
        model_name:          LLM-Modellname; leer → erstes verfügbares Modell.

    Returns:
        Erklärungstext als String (Fallback-Text bei Fehler).
    """
    if provider is None:
        from modules.llm_providers import get_provider
        provider = get_provider()

    if not model_name:
        try:
            models = provider.list_models()
            model_name = models[0] if models else ""
        except Exception:
            model_name = ""

    top3 = _top_features(features, feature_importances, n=3)
    prompt = _build_prompt(prediction, sentiment_score, top3)

    try:
        return provider.query(
            model=model_name,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.3,
        ).strip()
    except Exception as exc:
        logger.warning(f"Erklärungs-LLM-Aufruf fehlgeschlagen: {exc}")
        return _fallback_explanation(prediction, sentiment_score, top3)


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen
# ---------------------------------------------------------------------------

def _top_features(
    features: dict[str, float],
    importances: dict[str, float],
    n: int = 3,
) -> list[tuple[str, float, float]]:  # (name, value, importance)
    """
    Gibt die ``n`` wichtigsten Features als (name, wert, importance) zurück.
    Features, die nicht in ``features`` vorhanden sind, werden übersprungen.
    """
    ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    result = []
    for fname, imp in ranked:
        if fname in features:
            result.append((fname, features[fname], imp))
        if len(result) >= n:
            break
    return result


def _build_prompt(
    prediction: str,
    sentiment_score: float,
    top3: list[tuple[str, float, float]],
) -> str:
    """Baut den LLM-Prompt für die Erklärung."""
    signal_de = {
        "KAUFEN":    "Kauf-Signal",
        "VERKAUFEN": "Verkauf-Signal",
        "HALTEN":    "Halte-Signal",
    }.get(prediction, prediction)

    feature_lines = "\n".join(
        f"- {_FEATURE_LABELS.get(name, name)}: {_fmt_value(name, value)} "
        f"(Modell-Gewichtung: {imp:.0%})"
        for name, value, imp in top3
    )

    sentiment_desc = _sentiment_label(sentiment_score)

    return (
        f"Das ML-Modell gibt ein {signal_de}.\n\n"
        f"Die drei wichtigsten Einflussfaktoren:\n{feature_lines}\n\n"
        f"News-Sentiment der letzten Schlagzeilen: {sentiment_score:+.2f} ({sentiment_desc})\n\n"
        f"Erkläre diese Entscheidung in 2–3 verständlichen deutschen Sätzen "
        f"für einen Privatanleger. Beziehe dich konkret auf die genannten Faktoren."
    )


def _fmt_value(feature_name: str, value: float) -> str:
    """Formatiert einen Feature-Wert lesbar (z.B. RSI als Integer, Renditen in %)."""
    if feature_name == "rsi":
        return f"{value:.1f}"
    if feature_name in ("ret_1d", "ret_5d", "ret_20d", "sma_20", "sma_50",
                        "sma_cross", "volatility_20d"):
        return f"{value:+.2%}"
    if feature_name == "sentiment":
        return f"{value:+.2f}"
    return f"{value:.4f}"


def _sentiment_label(score: float) -> str:
    if score > 0.5:
        return "sehr positiv"
    if score > 0.2:
        return "positiv"
    if score > -0.2:
        return "neutral"
    if score > -0.5:
        return "negativ"
    return "sehr negativ"


def _fallback_explanation(
    prediction: str,
    sentiment_score: float,
    top3: list[tuple[str, float, float]],
) -> str:
    """Regelbasierter Fallback wenn LLM nicht erreichbar ist."""
    if not top3:
        return f"Modell empfiehlt {prediction}. Sentiment: {sentiment_score:+.2f}."

    top_name, top_val, _ = top3[0]
    label = _FEATURE_LABELS.get(top_name, top_name)
    sentiment_desc = _sentiment_label(sentiment_score)
    return (
        f"Modell empfiehlt {prediction}. "
        f"Stärkster Einflussfaktor: {label} ({_fmt_value(top_name, top_val)}). "
        f"News-Sentiment ist {sentiment_desc} ({sentiment_score:+.2f})."
    )
