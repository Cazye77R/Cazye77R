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
# Keine Module-zu-Modul-Importe – build_features ist hier inline definiert;
# ml_bundle und training_state werden von app.py übergeben.


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
    u, lower_val = upper.iloc[-1], lower.iloc[-1]
    if price < lower_val:
        return "KAUFEN", min(0.85, 0.5 + (lower_val - price) / (u - lower_val))
    if price > u:
        return "VERKAUFEN", min(0.85, 0.5 + (price - u) / (u - lower_val))
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
# ML-Feature-Berechnung (inline, kein Trainer-Import nötig)
# ---------------------------------------------------------------------------

def _build_features(df: pd.DataFrame, sentiment_score: float = 0.0) -> pd.DataFrame:
    """
    Berechnet numerische ML-Features aus OHLCV-Daten.

    Muss dieselben Spalten erzeugen wie trainer.build_features() —
    beide Funktionen werden zusammen geändert.

    Args:
        df:              OHLCV-DataFrame.
        sentiment_score: News-Sentiment-Score [-1, +1]; Standard 0.0 (neutral).
    """
    feat = pd.DataFrame(index=df.index)
    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]
    feat["ret_1d"]         = close.pct_change(1)
    feat["ret_5d"]         = close.pct_change(5)
    feat["ret_20d"]        = close.pct_change(20)
    feat["sma_20"]         = close.rolling(20).mean() / close - 1
    feat["sma_50"]         = close.rolling(50).mean() / close - 1
    feat["sma_cross"]      = feat["sma_20"] - feat["sma_50"]
    feat["volatility_20d"] = close.pct_change().rolling(20).std()
    feat["vol_ratio"]      = volume / volume.rolling(20).mean()
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    feat["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    feat["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    bb_mid = close.rolling(20).mean()
    feat["bb_pos"]    = (close - bb_mid) / (2 * close.rolling(20).std())
    feat["hl_range"]  = (high - low) / close
    feat["sentiment"] = float(sentiment_score)
    feat.dropna(inplace=True)
    return feat


# ---------------------------------------------------------------------------
# Haupt-Vorhersage
# ---------------------------------------------------------------------------

def predict(
    ticker: str,
    df: pd.DataFrame,
    method: str = "Auto (KI wählt)",
    horizon_days: int = 5,
    ml_bundle: Optional[dict] = None,
    training_state: Optional[dict] = None,
    sentiment_score: float = 0.0,
) -> Prediction:
    """
    ml_bundle:      Optional dict mit 'model' und 'scaler' (aus trainer.load_model).
    training_state: Optional dict mit 'accuracy' etc. (aus trainer.load_state).
    Beide werden von app.py übergeben – predictor importiert trainer NICHT mehr.
    """
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

    # --- ML-Modell (optional, Bundle von app.py übergeben) ---
    ml_prob: Optional[float] = None
    if ml_bundle:
        try:
            features = _build_features(df, sentiment_score=sentiment_score)
            if len(features) > 0:
                last_row = features.iloc[[-1]].values
                # Rückwärtskompatibilität: Modelle die vor dem Sentiment-Feature
                # trainiert wurden haben n_features_in_ == 12; wir degradieren
                # dann auf die ursprünglichen 12 Spalten ohne sentiment.
                expected = getattr(ml_bundle["scaler"], "n_features_in_", last_row.shape[1])
                if expected != last_row.shape[1]:
                    warnings.append(
                        "ML-Modell wurde vor Sentiment-Feature trainiert – "
                        "bitte Modell neu trainieren für volle Genauigkeit."
                    )
                    last_row = last_row[:, :expected]
                X = ml_bundle["scaler"].transform(last_row)
                ml_prob = float(ml_bundle["model"].predict_proba(X)[0][1])
                ml_score = (ml_prob - 0.5) * 2
                scores.append(ml_score * 0.8)
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

    model_acc = (training_state or {}).get("accuracy")
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
