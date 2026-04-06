"""
StockMind – Vorhersage-Logik
Kombiniert ML-Modell-Signale mit technischen Indikatoren zu einer
Gesamtbewertung und gibt strukturierte Prognosen zurück.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from modules.trainer import build_features, load_model, load_state


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class Prediction:
    ticker: str
    signal: str                       # "KAUFEN" | "HALTEN" | "VERKAUFEN"
    confidence: float                 # 0.0 – 1.0
    ml_probability: Optional[float]   # Rohe ML-Wahrscheinlichkeit (Anstieg)
    indicator_signals: dict           # Einzelsignale je Methode
    summary: str                      # Kurztextbeschreibung
    horizon_days: int = 5
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Technische Signal-Berechnung
# ---------------------------------------------------------------------------

def _sma_signal(df: pd.DataFrame) -> tuple[str, float]:
    close = df["Close"]
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    price = close.iloc[-1]
    if sma20 > sma50 and price > sma20:
        return "KAUFEN", 0.7
    if sma20 < sma50 and price < sma20:
        return "VERKAUFEN", 0.7
    return "HALTEN", 0.5


def _rsi_signal(df: pd.DataFrame) -> tuple[str, float]:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    if rsi < 30:
        return "KAUFEN", min(0.9, 0.5 + (30 - rsi) / 60)
    if rsi > 70:
        return "VERKAUFEN", min(0.9, 0.5 + (rsi - 70) / 60)
    return "HALTEN", 0.5


def _macd_signal(df: pd.DataFrame) -> tuple[str, float]:
    close = df["Close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    hist = (macd - signal_line).iloc[-3:]
    if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
        return "KAUFEN", 0.75
    if hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
        return "VERKAUFEN", 0.75
    return "HALTEN", 0.5


def _bollinger_signal(df: pd.DataFrame) -> tuple[str, float]:
    close = df["Close"]
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    price = close.iloc[-1]
    u, l = upper.iloc[-1], lower.iloc[-1]
    if price < l:
        return "KAUFEN", min(0.85, 0.5 + (l - price) / (u - l))
    if price > u:
        return "VERKAUFEN", min(0.85, 0.5 + (price - u) / (u - l))
    return "HALTEN", 0.5


SIGNAL_FUNCTIONS = {
    "SMA Crossover": _sma_signal,
    "RSI": _rsi_signal,
    "MACD": _macd_signal,
    "Bollinger Bands": _bollinger_signal,
}

SIGNAL_SCORE = {"KAUFEN": 1, "HALTEN": 0, "VERKAUFEN": -1}
SCORE_TO_SIGNAL = {1: "KAUFEN", 0: "HALTEN", -1: "VERKAUFEN"}


# ---------------------------------------------------------------------------
# Haupt-Vorhersage
# ---------------------------------------------------------------------------

def predict(
    ticker: str,
    df: pd.DataFrame,
    method: str = "Auto (KI wählt)",
    horizon_days: int = 5,
) -> Prediction:
    """
    Erstellt eine Vorhersage für einen Ticker.

    Args:
        ticker:       Aktien-Ticker
        df:           OHLCV-DataFrame (mind. 60 Zeilen)
        method:       Analysemethode aus config.ANALYSIS_METHODS
        horizon_days: Prognosehorizont in Tagen

    Returns:
        Prediction-Objekt mit Signal, Konfidenz und Einzelsignalen
    """
    warnings: list[str] = []
    indicator_signals: dict = {}

    # --- Technische Indikatoren ---
    if method == "Auto (KI wählt)":
        methods_to_run = list(SIGNAL_FUNCTIONS.keys())
    elif method in SIGNAL_FUNCTIONS:
        methods_to_run = [method]
    else:
        methods_to_run = list(SIGNAL_FUNCTIONS.keys())
        warnings.append(f"Methode '{method}' hat keine eigenständige Signal-Berechnung – alle Indikatoren verwendet.")

    scores = []
    for m in methods_to_run:
        try:
            sig, conf = SIGNAL_FUNCTIONS[m](df)
            indicator_signals[m] = {"signal": sig, "confidence": round(conf, 3)}
            scores.append(SIGNAL_SCORE[sig] * conf)
        except Exception as exc:
            warnings.append(f"{m}: Fehler – {exc}")

    # --- ML-Modell (optional) ---
    ml_prob: Optional[float] = None
    bundle = load_model(ticker)
    if bundle:
        try:
            features = build_features(df)
            if len(features) > 0:
                X = bundle["scaler"].transform(features.iloc[[-1]].values)
                ml_prob = float(bundle["model"].predict_proba(X)[0][1])
                ml_score = (ml_prob - 0.5) * 2          # Skalierung auf [-1, 1]
                scores.append(ml_score * 0.8)            # ML bekommt Gewicht 0.8
                indicator_signals["ML-Modell"] = {
                    "signal": "KAUFEN" if ml_prob > 0.55 else ("VERKAUFEN" if ml_prob < 0.45 else "HALTEN"),
                    "confidence": round(abs(ml_prob - 0.5) * 2, 3),
                    "probability": round(ml_prob, 3),
                }
        except Exception as exc:
            warnings.append(f"ML-Modell: {exc}")

    # --- Aggregation ---
    if not scores:
        return Prediction(
            ticker=ticker, signal="HALTEN", confidence=0.0,
            ml_probability=ml_prob, indicator_signals={},
            summary="Nicht genug Daten für eine Vorhersage.",
            horizon_days=horizon_days, warnings=warnings,
        )

    avg_score = float(np.mean(scores))
    abs_score = abs(avg_score)
    confidence = min(1.0, abs_score)

    if avg_score > 0.15:
        signal = "KAUFEN"
    elif avg_score < -0.15:
        signal = "VERKAUFEN"
    else:
        signal = "HALTEN"

    state = load_state(ticker)
    model_acc = state.get("accuracy")
    acc_str = f" (Modell-Genauigkeit: {model_acc:.1%})" if model_acc else ""

    summary = (
        f"{signal}-Signal mit {confidence:.0%} Konfidenz "
        f"für {ticker} über {horizon_days} Tage{acc_str}."
    )

    return Prediction(
        ticker=ticker,
        signal=signal,
        confidence=round(confidence, 3),
        ml_probability=ml_prob,
        indicator_signals=indicator_signals,
        summary=summary,
        horizon_days=horizon_days,
        warnings=warnings,
    )


def build_context_string(ticker: str, df: pd.DataFrame, prediction: Prediction) -> str:
    """
    Erstellt eine Textzusammenfassung der aktuellen Marktlage für den LLM-Prompt.
    """
    close = df["Close"]
    lines = [
        f"Ticker: {ticker}",
        f"Aktueller Kurs: {close.iloc[-1]:.2f}",
        f"7-Tage-Veränderung: {close.pct_change(7).iloc[-1]:.2%}",
        f"30-Tage-Veränderung: {close.pct_change(30).iloc[-1]:.2%}",
        f"52-Wochen-Hoch: {close.rolling(252).max().iloc[-1]:.2f}",
        f"52-Wochen-Tief: {close.rolling(252).min().iloc[-1]:.2f}",
        "",
        "Indikatoren:",
    ]
    for name, sig in prediction.indicator_signals.items():
        conf = sig.get("confidence", "–")
        prob = f" (p={sig['probability']:.2f})" if "probability" in sig else ""
        lines.append(f"  {name}: {sig['signal']} (Konfidenz {conf:.0%}{prob})")
    if prediction.warnings:
        lines.append("\nWarnungen: " + "; ".join(prediction.warnings))
    return "\n".join(lines)
