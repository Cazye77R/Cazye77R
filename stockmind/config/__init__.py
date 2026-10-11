"""
StockMind – Zentrale Konfiguration

Importiert alles aus den thematischen Untermodulen.
Alle bestehenden ``from config import X`` Statements funktionieren unverändert.
"""

from __future__ import annotations

import os

# ── .env laden ────────────────────────────────────────────────────────────────
# python-dotenv ist optional. Ohne dotenv werden Umgebungsvariablen direkt aus
# dem Prozess gelesen (CI, Docker, systemd). Kein Hard-Fail.
try:
    from dotenv import load_dotenv as _load_dotenv  # noqa: PLC0415

    _dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    _load_dotenv(dotenv_path=_dotenv_path, override=False)
except ImportError:
    # python-dotenv nicht installiert – env-Variablen müssen extern gesetzt sein
    pass

# ── Thematische Re-Exporte ─────────────────────────────────────────────────────
# Reihenfolge ist relevant: dotenv muss VOR den os.getenv()-Aufrufen laufen.
from config.models import *  # noqa: F401, F403, E402
from config.storage import *  # noqa: F401, F403, E402
from config.trading import *  # noqa: F401, F403, E402

# ── App-Metadaten ──────────────────────────────────────────────────────────────
APP_TITLE: str = "StockMind"
APP_ICON: str = "🧠"
APP_VERSION: str = "0.1.0"
