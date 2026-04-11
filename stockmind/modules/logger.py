"""
StockMind – Zentrale Logger-Konfiguration (stdlib logging)

Importiere überall so:
    from modules.logger import logger
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

_LEVEL_NAME: str = os.getenv("LOG_LEVEL", "INFO").upper()
_LEVEL: int = getattr(logging, _LEVEL_NAME, logging.INFO)

_FMT = "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s"
_DATEFMT = "%H:%M:%S"

# Log-Verzeichnis relativ zu dieser Datei (modules/ → data/logs/)
_LOG_DIR: Path = Path(__file__).parent.parent / "data" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Logger aufsetzen ──────────────────────────────────────────────────────────

logger = logging.getLogger("stockmind")
logger.setLevel(_LEVEL)

# Doppelt-Konfiguration verhindern (z. B. bei Streamlit-Reruns)
if not logger.handlers:
    _formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # Konsole
    _console = logging.StreamHandler(sys.stderr)
    _console.setLevel(_LEVEL)
    _console.setFormatter(_formatter)
    logger.addHandler(_console)

    # Datei – tägliche Rotation um Mitternacht, 7 Tage Retention
    _file = TimedRotatingFileHandler(
        _LOG_DIR / "stockmind.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    _file.setLevel(_LEVEL)
    _file.setFormatter(_formatter)
    _file.suffix = "%Y-%m-%d"
    logger.addHandler(_file)

# Propagation abschalten – kein Doppel-Output über den Root-Logger
logger.propagate = False
