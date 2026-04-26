"""Handels- und Analyse-Konstanten."""

from __future__ import annotations

import os

# --- Handelskosten ---
ORDER_COST_EUR: float = 5.0
SPREAD_PERCENT: float = 0.1

# --- Paper-Trading ---
DEFAULT_BUDGET_EUR: float = 10_000.0

# --- Easter Egg: Lambo-Zielpreis ---
LAMBO_PRICE_EUR: float = 536_000.0  # Lamborghini Aventador SVJ Basispreis DE

# --- Analyse-Methoden ---
ANALYSIS_METHODS: list[str] = [
    "SMA Crossover",
    "RSI",
    "MACD",
    "Bollinger Bands",
    "Support/Resistance",
    "Candlestick Patterns",
    "Auto (KI wählt)",
]

# --- Technische Indikatoren – Standardparameter ---
SMA_SHORT: int = 20
SMA_LONG: int = 50
RSI_PERIOD: int = 14
RSI_OVERBOUGHT: int = 70
RSI_OVERSOLD: int = 30
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9
BOLLINGER_PERIOD: int = 20
BOLLINGER_STD: float = 2.0

# --- UCB1-Algorithmus (Auto-Training) ---
# Exploration-Konstante: höher = mehr neue Methoden testen, niedriger = mehr exploitieren
# sqrt(2) ≈ 1.414 ist der theoretische Standardwert für UCB1
EXPLORATION_CONSTANT: float = float(os.getenv("EXPLORATION_CONSTANT", "1.414"))

# --- Feature-Flags ---
# Easter Eggs (Lambo-Währung, Konfetti, versteckte Überraschungen)
ENABLE_EASTER_EGGS: bool = os.getenv("ENABLE_EASTER_EGGS", "true").lower() == "true"

# --- Bandit-Algorithmen ---
# Discount-Faktor für Discounted-UCB1: γ ∈ (0, 1)
# Niedrigerer Wert = stärkere Gewichtung neuer Rewards (aggressiverer Vergiss-Effekt)
DUCB_GAMMA: float = float(os.getenv("DUCB_GAMMA", "0.95"))
# Basis-Spread in Prozent (fixed Komponente)
SLIPPAGE_BASE_PCT:          float = float(os.getenv("SLIPPAGE_BASE_PCT",          "0.05"))
# Volumen-Faktor k: slippage += k * (order_size / avg_daily_volume)
SLIPPAGE_VOLUME_FACTOR:     float = float(os.getenv("SLIPPAGE_VOLUME_FACTOR",     "0.1"))
# Fallback für avg_daily_volume wenn kein echtes Volumen vorhanden
SLIPPAGE_DAILY_VOLUME_DEFAULT: float = float(os.getenv("SLIPPAGE_DAILY_VOLUME_DEFAULT", "1000000.0"))

# --- Risk Management ---
MAX_RISK_PER_TRADE_PCT:       float = float(os.getenv("MAX_RISK_PER_TRADE_PCT",       "2.0"))
MAX_POSITION_SIZE_PCT:        float = float(os.getenv("MAX_POSITION_SIZE_PCT",        "25.0"))
MAX_DRAWDOWN_PCT:             float = float(os.getenv("MAX_DRAWDOWN_PCT",             "15.0"))
MAX_CORRELATED_EXPOSURE_PCT:  float = float(os.getenv("MAX_CORRELATED_EXPOSURE_PCT",  "40.0"))
STOP_LOSS_ATR_MULTIPLE:       float = float(os.getenv("STOP_LOSS_ATR_MULTIPLE",       "2.0"))
TAKE_PROFIT_ATR_MULTIPLE:     float = float(os.getenv("TAKE_PROFIT_ATR_MULTIPLE",     "3.0"))
