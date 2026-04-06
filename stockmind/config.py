"""
StockMind – Zentrale Konfiguration
"""

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

# --- Cache ---
CACHE_TTL_HOURS: int = 24           # Lebensdauer des OHLCV-Cache in Stunden

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

# --- Ollama API ---
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_TIMEOUT_S: int = 120

# --- App-Metadaten ---
APP_TITLE: str = "StockMind"
APP_ICON: str = "🧠"
APP_VERSION: str = "0.1.0"
