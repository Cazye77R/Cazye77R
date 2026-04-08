"""
StockMind – Zentrale Konfiguration

Werte, die via .env überschreibbar sind, werden mit os.getenv() geladen.
Alle anderen Konstanten bleiben hardcodiert und sind nicht umgebungsabhängig.
"""

import logging
import os

from dotenv import load_dotenv

# Lade .env aus dem Verzeichnis dieser Datei (stockmind/.env)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ── Via .env konfigurierbar ───────────────────────────────────────────────────

# Ollama API – überschreibbar per OLLAMA_HOST=http://my-server:11434
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Cache-Lebensdauer in Stunden – überschreibbar per CACHE_TTL_HOURS=0
CACHE_TTL_HOURS: int = int(os.getenv("CACHE_TTL_HOURS", "24"))

# Log-Level – überschreibbar per LOG_LEVEL=DEBUG
LOG_LEVEL: int = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

# Logging einmalig konfigurieren
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s %(name)s: %(message)s")

# ── Unveränderliche Konstanten ────────────────────────────────────────────────

# --- Handelskosten ---
ORDER_COST_EUR: float = 5.0          # Standard-Ordergebühr in €
SPREAD_PERCENT: float = 0.1          # Standard-Spread in %

# --- Paper-Trading ---
DEFAULT_BUDGET_EUR: float = 10_000.0  # Startkapital für Paper-Trading

# --- Easter Egg: Lambo-Währung ---
LAMBO_PRICE_EUR: float = 536_000.0   # Lamborghini Aventador SVJ Basispreis DE

# --- Ollama-Modelle ---
AVAILABLE_MODELS: list[str] = [
    "llama3",
    "mistral",
    "phi3",
    "gemma2",
    "qwen2",
]
DEFAULT_MODEL: str = "llama3"
OLLAMA_TIMEOUT_S: int = 120

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

# --- Dateipfade ---
DATA_DIR: str = "data"
TRAINING_STATE_DIR: str = "data/training_state"
PORTFOLIO_DIR: str = "data/portfolio"
CACHE_DIR: str = "data/cache"

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

# --- Daten-Download ---
DEFAULT_PERIOD: str = "1y"           # Standardzeitraum für yfinance
DEFAULT_INTERVAL: str = "1d"         # Tages-Kerzen

# --- App-Metadaten ---
APP_TITLE: str = "StockMind"
APP_ICON: str = "🧠"
APP_VERSION: str = "0.1.0"
