"""
StockMind – Zentrale Logger-Konfiguration (loguru)

Importiere überall so:
    from modules.logger import logger
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

# ── Konfiguration ─────────────────────────────────────────────────────────────

_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
_FMT: str = "{time:HH:mm:ss} | {level:<8} | {module} | {message}"

# Log-Verzeichnis relativ zu dieser Datei (modules/ → data/logs/)
_LOG_DIR: Path = Path(__file__).parent.parent / "data" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Standard-Sink entfernen, dann sauber neu konfigurieren
logger.remove()

# Konsole
logger.add(
    sys.stderr,
    level=_LEVEL,
    format=_FMT,
    colorize=True,
)

# Datei – tägliche Rotation, 7 Tage Retention
logger.add(
    _LOG_DIR / "stockmind_{time:YYYY-MM-DD}.log",
    level=_LEVEL,
    format=_FMT,
    rotation="00:00",       # täglich um Mitternacht rotieren
    retention="7 days",
    encoding="utf-8",
    enqueue=True,           # thread-sicher
)
