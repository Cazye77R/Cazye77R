"""
StockMind – Trainings-Engine
Verwaltet Trainingszyklen per Aktie, persistiert den Zustand und berechnet
einfache ML-Features für spätere Vorhersagen.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import pickle

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import TRAINING_STATE_DIR


# ---------------------------------------------------------------------------
# Zustandsverwaltung
# ---------------------------------------------------------------------------

def _state_path(ticker: str) -> Path:
    path = Path(TRAINING_STATE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{ticker.upper()}.json"


def _model_path(ticker: str) -> Path:
    path = Path(TRAINING_STATE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{ticker.upper()}_model.pkl"


def load_state(ticker: str) -> dict:
    """Lädt den Trainingszustand für einen Ticker. Gibt leeren Zustand zurück wenn keiner existiert."""
    p = _state_path(ticker)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "ticker": ticker.upper(),
        "cycles": 0,
        "last_trained": None,
        "accuracy": None,
        "feature_importance": {},
        "training_log": [],
    }


def save_state(ticker: str, state: dict) -> None:
    """Persistiert den Trainingszustand als JSON."""
    with open(_state_path(ticker), "w") as f:
        json.dump(state, f, indent=2, default=str)


def list_trained_stocks() -> list[str]:
    """Gibt alle Ticker zurück für die ein Trainingszustand existiert."""
    p = Path(TRAINING_STATE_DIR)
    if not p.exists():
        return []
    return [f.stem for f in p.glob("*.json") if not f.stem.endswith("_model")]


# ---------------------------------------------------------------------------
# Feature-Engineering
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet ML-Features aus OHLCV-Daten.
    Input: DataFrame mit Spalten Open, High, Low, Close, Volume
    Output: DataFrame mit Feature-Spalten (NaN-Zeilen werden gedroppt)
    """
    feat = pd.DataFrame(index=df.index)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # Preisveränderungen
    feat["ret_1d"] = close.pct_change(1)
    feat["ret_5d"] = close.pct_change(5)
    feat["ret_20d"] = close.pct_change(20)

    # Gleitende Durchschnitte
    feat["sma_20"] = close.rolling(20).mean() / close - 1
    feat["sma_50"] = close.rolling(50).mean() / close - 1
    feat["sma_cross"] = feat["sma_20"] - feat["sma_50"]

    # Volatilität
    feat["volatility_20d"] = close.pct_change().rolling(20).std()

    # Volumen-Ratio
    feat["vol_ratio"] = volume / volume.rolling(20).mean()

    # RSI (manuell, ohne ta-Abhängigkeit für Features)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    feat["rsi"] = 100 - (100 / (1 + rs))

    # MACD-Signal
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    feat["macd_hist"] = macd - signal

    # Bollinger Band Position
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    feat["bb_pos"] = (close - bb_mid) / (2 * bb_std)

    # Hoch/Tief-Abstand
    feat["hl_range"] = (high - low) / close

    feat.dropna(inplace=True)
    return feat


def build_labels(df: pd.DataFrame, horizon: int = 5, threshold: float = 0.01) -> pd.Series:
    """
    Erstellt binäre Labels: 1 = Kurs steigt um ≥threshold in horizon Tagen, 0 = sonst.
    """
    future_ret = df["Close"].pct_change(horizon).shift(-horizon)
    return (future_ret >= threshold).astype(int)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(ticker: str, df: pd.DataFrame, horizon: int = 5) -> dict:
    """
    Trainiert ein GradientBoosting-Modell für einen Ticker und persistiert Modell + Zustand.

    Args:
        ticker:  Aktien-Ticker
        df:      OHLCV-DataFrame
        horizon: Vorhergesagter Zeithorizont in Tagen

    Returns:
        Aktualisierter Zustandsdict mit Accuracy und Feature-Importance
    """
    state = load_state(ticker)

    features = build_features(df)
    labels = build_labels(df, horizon=horizon)

    # Gemeinsamen Index sicherstellen
    idx = features.index.intersection(labels.index)
    X = features.loc[idx].values
    y = labels.loc[idx].values

    if len(X) < 60:
        raise ValueError(f"Zu wenige Datenpunkte für Training: {len(X)} (mind. 60 nötig)")

    # Train/Test-Split (letzten 20% als Test)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    model.fit(X_train_s, y_train)
    accuracy = float(model.score(X_test_s, y_test))

    # Modell + Scaler persistieren
    with open(_model_path(ticker), "wb") as f:
        pickle.dump({"model": model, "scaler": scaler, "feature_names": list(features.columns)}, f)

    # Zustand aktualisieren
    state["cycles"] = state.get("cycles", 0) + 1
    state["last_trained"] = datetime.now().isoformat()
    state["accuracy"] = round(accuracy, 4)
    state["feature_importance"] = dict(
        zip(features.columns, [round(v, 4) for v in model.feature_importances_])
    )
    state["training_log"].append({
        "cycle": state["cycles"],
        "timestamp": state["last_trained"],
        "accuracy": state["accuracy"],
        "samples": len(X),
        "horizon_days": horizon,
    })
    save_state(ticker, state)
    return state


def load_model(ticker: str) -> Optional[dict]:
    """Lädt gespeichertes Modell + Scaler. Gibt None zurück wenn keines existiert."""
    p = _model_path(ticker)
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)
