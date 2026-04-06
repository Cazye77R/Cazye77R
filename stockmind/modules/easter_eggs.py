"""
StockMind – Easter Egg Logik
Inklusive Lambo-Währung, versteckten Nachrichten und Trigger-Erkennung.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import LAMBO_PRICE_EUR


# ---------------------------------------------------------------------------
# Lambo-Währung
# ---------------------------------------------------------------------------

def eur_to_lambo(eur: float) -> float:
    """Rechnet EUR in Lambos (Aventador SVJ) um."""
    return eur / LAMBO_PRICE_EUR


def lambo_to_eur(lambos: float) -> float:
    """Rechnet Lambos in EUR um."""
    return lambos * LAMBO_PRICE_EUR


def format_lambo(eur: float) -> str:
    """Gibt einen formatierten Lambo-String zurück, z.B. '0.0187 🏎️ Lambos'."""
    lambos = eur_to_lambo(eur)
    if lambos >= 1:
        return f"**{lambos:.2f} 🏎️ Lambos**"
    elif lambos >= 0.01:
        return f"**{lambos:.4f} 🏎️ Lambos** ({lambos * 100:.2f}% eines Lambos)"
    else:
        return f"**{lambos:.6f} 🏎️ Lambos** (noch ein weiter Weg...)"


def lambo_progress_bar(eur: float) -> tuple[float, str]:
    """
    Gibt (Prozent 0-100, Motivationstext) für den Weg zum ersten Lambo zurück.
    """
    pct = min(100.0, eur / LAMBO_PRICE_EUR * 100)
    if pct >= 100:
        msg = "🏎️ LAMBO ACHIEVED! Herzlichen Glückwunsch!"
    elif pct >= 75:
        msg = "🔥 Fast da! Die Schlüssel warten schon..."
    elif pct >= 50:
        msg = "💪 Halbzeit! Bleib dabei!"
    elif pct >= 25:
        msg = "📈 Gut unterwegs! Weiter so!"
    elif pct >= 10:
        msg = "🌱 Anfänge sind gut! Geduld zahlt sich aus."
    else:
        msg = "🐣 Jede Reise beginnt mit dem ersten Schritt."
    return pct, msg


# ---------------------------------------------------------------------------
# Easter Egg Trigger
# ---------------------------------------------------------------------------

@dataclass
class EasterEgg:
    id: str
    title: str
    message: str
    emoji: str = "🥚"


EASTER_EGGS: list[EasterEgg] = [
    EasterEgg(
        id="moon",
        title="🚀 To the Moon!",
        message=(
            "Das Modell sagt: 📈📈📈\n"
            "Aber vergiss nicht: Was rauf geht, kann auch runterkommen. "
            "Anlageberatung? Nein. Entertainmentwert? Definitiv."
        ),
        emoji="🚀",
    ),
    EasterEgg(
        id="dip",
        title="Buy the Dip™",
        message=(
            "Der Kurs ist gefallen. Die KI sieht eine Chance.\n"
            "Oder eine Falle. Wer weiß das schon? 🎰\n"
            "Disclaimer: StockMind haftet nicht für verlorene Lambos."
        ),
        emoji="🛒",
    ),
    EasterEgg(
        id="diamond_hands",
        title="💎 Diamond Hands erkannt!",
        message=(
            "Du hältst diese Aktie schon sehr lange.\n"
            "Entweder bist du ein Genie oder ein geduldiger Mensch. "
            "Beides ist respektabel. 💎🙌"
        ),
        emoji="💎",
    ),
    EasterEgg(
        id="yolo",
        title="YOLO-Modus aktiviert",
        message=(
            "Du hast 100% deines Portfolios in eine Aktie gesteckt.\n"
            "Mutig. Sehr mutig. 🎲\n"
            "Fun Fact: Diversifikation existiert aus einem Grund."
        ),
        emoji="🎲",
    ),
    EasterEgg(
        id="patience",
        title="🧘 Zen-Investor",
        message=(
            "Du hast heute keine einzige Order ausgeführt.\n"
            "Manchmal ist Nichtstun die beste Strategie. 🧘\n"
            "Warren Buffett würde stolz sein."
        ),
        emoji="🧘",
    ),
    EasterEgg(
        id="first_profit",
        title="🎉 Erster Gewinn!",
        message=(
            "Dein erster realisierter Gewinn! 🎊\n"
            "Das ist erst der Anfang. Der Lambo ist jetzt "
            f"{LAMBO_PRICE_EUR/1000:.0f}k€ entfernt... aber du bist unterwegs!"
        ),
        emoji="🎉",
    ),
    EasterEgg(
        id="ten_trades",
        title="📊 Erfahrener Trader",
        message=(
            "10 Trades abgeschlossen!\n"
            "Du hast genug Erfahrung, um zu wissen, dass Märkte unvorhersehbar sind. "
            "Oder? 😄"
        ),
        emoji="📊",
    ),
]

EGG_LOOKUP = {egg.id: egg for egg in EASTER_EGGS}


# ---------------------------------------------------------------------------
# Trigger-Logik
# ---------------------------------------------------------------------------

def check_triggers(
    total_value: float,
    total_return_pct: float,
    num_trades: int,
    positions: list[dict],
    previous_value: float = 0.0,
) -> list[EasterEgg]:
    """
    Prüft auf Easter-Egg-Bedingungen und gibt ausgelöste Eggs zurück.

    Args:
        total_value:       Aktueller Gesamtwert
        total_return_pct:  Gesamtrendite in %
        num_trades:        Anzahl bisheriger Trades
        positions:         Aktuelle Positionen (Liste von Dicts)
        previous_value:    Vorheriger Gesamtwert (für Gewinndetektierung)

    Returns:
        Liste der ausgelösten EasterEgg-Objekte
    """
    triggered = []

    # Steigende Performance
    if total_return_pct >= 20:
        triggered.append(EGG_LOOKUP["moon"])

    # Verlust (Buy the Dip)
    if total_return_pct <= -10:
        triggered.append(EGG_LOOKUP["dip"])

    # Erster Gewinn (Wert stieg über Startkapital)
    if previous_value > 0 and previous_value < 10_000 and total_value >= 10_000:
        triggered.append(EGG_LOOKUP["first_profit"])

    # YOLO: Alles in eine Aktie
    if len(positions) == 1 and positions[0].get("value", 0) / total_value > 0.95:
        triggered.append(EGG_LOOKUP["yolo"])

    # 10 Trades Meilenstein
    if num_trades == 10:
        triggered.append(EGG_LOOKUP["ten_trades"])

    return triggered


# ---------------------------------------------------------------------------
# Zufällige Motivationsnachrichten
# ---------------------------------------------------------------------------

MOTIVATIONS = [
    "📊 Daten lügen nicht. Menschen interpretieren sie falsch.",
    "💡 Tipp: Vergangenheit ist kein Indikator für die Zukunft – aber ignorieren wäre auch dumm.",
    "🤖 Die KI analysiert. Du entscheidest. Gemeinsam vielleicht klüger.",
    "⚠️ Keine Anlageberatung. Ernstlich.",
    "🏎️ Jeden Tag ein Stück näher am Lambo... oder auch nicht.",
    "📉 Buy high, sell low – niemand will das, aber viele tun es.",
    "🧠 StockMind denkt mit. Aber dein Geld, deine Entscheidung.",
    "📅 Märkte sind langfristig aufwärts gerichtet. Kurzfristig: Chaos.",
]


def random_motivation() -> str:
    return random.choice(MOTIVATIONS)
