"""
StockMind – Zentrale Konfiguration

Importiert alles aus den thematischen Untermodulen.
Alle bestehenden ``from config import X`` Statements funktionieren unverändert.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# .env aus dem stockmind/-Verzeichnis laden (eine Ebene über config/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Thematische Re-Exporte – Reihenfolge ist relevant (dotenv muss vor os.getenv laufen)
from config.trading import *  # noqa: F401, F403, E402
from config.models import *   # noqa: F401, F403, E402
from config.storage import *  # noqa: F401, F403, E402

# --- App-Metadaten ---
APP_TITLE: str = "StockMind"
APP_ICON: str = "🧠"
APP_VERSION: str = "0.1.0"
