"""Handels- und Analyse-Konstanten."""

from __future__ import annotations

import logging
import os


def _env_float(name: str, default: float, lo: float | None = None, hi: float | None = None) -> float:
    """
    Liest eine Float-Env-Variable robust: unparsebare oder außerhalb der
    Grenzen liegende Werte fallen mit Warnung auf den Default zurück –
    ein Tippfehler in .env darf die App nicht beim Import crashen.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = float(raw)
    except ValueError:
        logging.getLogger("stockmind").warning(
            f"Env {name}={raw!r} ist keine Zahl – Default {default} wird verwendet."
        )
        return default
    if (lo is not None and val < lo) or (hi is not None and val > hi):
        logging.getLogger("stockmind").warning(
            f"Env {name}={val} außerhalb [{lo}, {hi}] – Default {default} wird verwendet."
        )
        return default
    return val

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
EXPLORATION_CONSTANT: float = _env_float("EXPLORATION_CONSTANT", 1.414, lo=0.0)

# --- Feature-Flags ---
# Easter Eggs (Lambo-Währung, Konfetti, versteckte Überraschungen)
ENABLE_EASTER_EGGS: bool = os.getenv("ENABLE_EASTER_EGGS", "true").lower() == "true"

# --- Bandit-Algorithmen ---
# Discount-Faktor für Discounted-UCB1: γ ∈ (0, 1)
# Niedrigerer Wert = stärkere Gewichtung neuer Rewards (aggressiverer Vergiss-Effekt)
DUCB_GAMMA: float = _env_float("DUCB_GAMMA", 0.95, lo=0.0001, hi=0.9999)
# Basis-Spread in Prozent (fixed Komponente)
SLIPPAGE_BASE_PCT:          float = _env_float("SLIPPAGE_BASE_PCT", 0.05, lo=0.0)
# Volumen-Faktor k: slippage += k * (order_size / avg_daily_volume)
SLIPPAGE_VOLUME_FACTOR:     float = _env_float("SLIPPAGE_VOLUME_FACTOR", 0.1, lo=0.0)
# Fallback für avg_daily_volume wenn kein echtes Volumen vorhanden
SLIPPAGE_DAILY_VOLUME_DEFAULT: float = _env_float("SLIPPAGE_DAILY_VOLUME_DEFAULT", 1_000_000.0, lo=1.0)

# --- Risk Management ---
MAX_RISK_PER_TRADE_PCT:       float = _env_float("MAX_RISK_PER_TRADE_PCT", 2.0, lo=0.1, hi=100.0)
MAX_POSITION_SIZE_PCT:        float = _env_float("MAX_POSITION_SIZE_PCT", 25.0, lo=1.0, hi=100.0)
MAX_DRAWDOWN_PCT:             float = _env_float("MAX_DRAWDOWN_PCT", 15.0, lo=1.0, hi=100.0)
MAX_CORRELATED_EXPOSURE_PCT:  float = _env_float("MAX_CORRELATED_EXPOSURE_PCT", 40.0, lo=1.0, hi=100.0)
STOP_LOSS_ATR_MULTIPLE:       float = _env_float("STOP_LOSS_ATR_MULTIPLE", 2.0, lo=0.1)
TAKE_PROFIT_ATR_MULTIPLE:     float = _env_float("TAKE_PROFIT_ATR_MULTIPLE", 3.0, lo=0.1)
