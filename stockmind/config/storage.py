"""Pfad- und Cache-Konstanten (lädt CACHE_TTL_HOURS + LOG_LEVEL aus der Umgebung)."""

from __future__ import annotations

import logging
import os

# --- Dateipfade ---
DATA_DIR: str = "data"
TRAINING_STATE_DIR: str = "data/training_state"
PORTFOLIO_DIR: str = "data/portfolio"
CACHE_DIR: str = "data/cache"

# --- Cache ---
# Überschreibbar per CACHE_TTL_HOURS=0 in .env (0 = kein Cache)
try:
    CACHE_TTL_HOURS: int = max(0, int(os.getenv("CACHE_TTL_HOURS", "24")))
except ValueError:
    logging.getLogger("stockmind").warning(
        f"Env CACHE_TTL_HOURS={os.getenv('CACHE_TTL_HOURS')!r} ungültig – Default 24."
    )
    CACHE_TTL_HOURS = 24

# --- Daten-Download ---
DEFAULT_PERIOD: str = "1y"
DEFAULT_INTERVAL: str = "1d"

# --- Logging ---
# Überschreibbar per LOG_LEVEL=DEBUG in .env.
# Kein logging.basicConfig hier – das würde einen konkurrierenden Root-Handler
# neben dem dedizierten Setup in modules/logger.py installieren.
LOG_LEVEL: int = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
