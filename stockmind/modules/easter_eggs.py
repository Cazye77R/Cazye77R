"""
StockMind – Easter Egg Logik
Währungs-Easter-Egg mit Klick-Counter, zufällige und konditionelle Easter Eggs,
Trigger-Erkennung, Lambo-Konverter.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import ENABLE_EASTER_EGGS, LAMBO_PRICE_EUR


# ===========================================================================
# 1. Währungs-Easter-Egg
# ===========================================================================

# Verfügbare Anzeigewährungen (Reihenfolge = Auswahl-Reihenfolge in der UI)
CURRENCIES: list[str] = [
    "EUR €",
    "USD $",
    "🍕 Pizzen (12€)",
    "☕ Kaffee (3.50€)",
    "🏎️ Lambos (536.000€)",
    "🚀 Raketen-Emojis",
]

# Anzahl versteckter Klicks auf das Portfolio-Total bis die Auswahl erscheint
CURRENCY_UNLOCK_CLICKS: int = 7

# Markierung für app.py um st.balloons() auszulösen
CONFETTI_MARKER: str = "[KONFETTI]"

# Ungefährer EUR→USD Kurs (statisch, kein API-Call nötig)
_EUR_USD_RATE: float = 1.08

# Preis-Referenzen je Nicht-Euro-Währung
_PIZZA_EUR:   float = 12.0
_COFFEE_EUR:  float = 3.50
_MAX_ROCKETS: int   = 60     # Maximal angezeigte 🚀 (verhindert UI-Overflow)


def get_currency_display(eur_value: float, currency: str) -> str:
    """
    Konvertiert einen EUR-Betrag in die gewünschte Anzeige-Währung.

    Args:
        eur_value: Portfolio-Wert in EUR
        currency:  Einer der Strings aus CURRENCIES

    Returns:
        Formatierter Anzeigestring, z.B. "852 🍕 Pizzen" oder "0.0191 🏎️ Lambos"

    Beispiele:
        get_currency_display(10_234.56, "EUR €")          → "10.234,56 €"
        get_currency_display(10_234.56, "🍕 Pizzen (12€)")  → "852 🍕 Pizzen"
        get_currency_display(10_234.56, "🏎️ Lambos (536.000€)") → "0.0191 🏎️ Lambos"
    """
    # Feature-Flag: Bei deaktiviertem Easter Egg immer plain EUR zurückgeben
    if not ENABLE_EASTER_EGGS:
        return f"{eur_value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    if currency == "EUR €":
        return f"{eur_value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    if currency == "USD $":
        usd = eur_value * _EUR_USD_RATE
        return f"${usd:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if currency == "🍕 Pizzen (12€)":
        count = eur_value / _PIZZA_EUR
        return f"{count:,.0f} 🍕 Pizzen"

    if currency == "☕ Kaffee (3.50€)":
        count = eur_value / _COFFEE_EUR
        return f"{count:,.0f} ☕ Kaffee"

    if currency.startswith("🏎️ Lambos"):
        lambos = eur_value / LAMBO_PRICE_EUR
        if lambos >= 1.0:
            return f"{lambos:.4f} 🏎️ Lambos (ZIEL ERREICHT! 🎉)"
        if lambos >= 0.01:
            return f"{lambos:.4f} 🏎️ Lambos ({lambos * 100:.2f}% eines Lambos)"
        return f"{lambos:.6f} 🏎️ Lambos (noch ein langer Weg…)"

    if currency == "🚀 Raketen-Emojis":
        # 1 Rakete = 200 €, Wert per Zeichen begrenzt
        count = max(1, min(_MAX_ROCKETS, int(eur_value / 200)))
        extra = "" if eur_value / 200 <= _MAX_ROCKETS else f" (+{int(eur_value/200) - _MAX_ROCKETS} mehr)"
        return f"{'🚀' * count}{extra}"

    # Fallback
    return f"{eur_value:,.2f} €"


def currency_tooltip(currency: str) -> str:
    """Gibt einen erklärenden Tooltip-Text für eine Währung zurück."""
    tips = {
        "EUR €":               "Der langweilige Euro. Funktioniert trotzdem.",
        "USD $":               f"US-Dollar (Kurs ~{_EUR_USD_RATE:.2f} USD/EUR).",
        "🍕 Pizzen (12€)":    "Eine ordentliche Margherita für 12 €.",
        "☕ Kaffee (3.50€)":  "Flat White beim Hipster-Café um die Ecke.",
        "🏎️ Lambos (536.000€)": "Lamborghini Aventador SVJ – Basispreis Deutschland.",
        "🚀 Raketen-Emojis":  "Jede Rakete repräsentiert 200 €. Einfach weil wir es können.",
    }
    return tips.get(currency, "")


# ===========================================================================
# 2. & 3.  check_easter_egg
# ===========================================================================

# Sonderfälle erhalten diese Priorität (niedrigere Zahl = höhere Priorität)
_PRIORITY_LAMBO    = 1
_PRIORITY_100CYC   = 2
_PRIORITY_AI_WALL  = 3
_PRIORITY_BUST     = 4
_PRIORITY_RANDOM   = 99


def check_easter_egg(context: dict) -> Optional[str]:
    """
    Prüft alle Easter-Egg-Bedingungen und gibt den Text des
    höchstpriorisierten ausgelösten Eggs zurück, oder None.

    Erwartete context-Schlüssel (alle optional, fehlende → keine Prüfung):
        cycles            (int)   – Anzahl abgeschlossener Trainingszyklen
        previous_cycles   (int)   – Zyklen beim letzten Aufruf (für Milestone-Erkennung)
        accuracy          (float) – Aktuelle Modell-Genauigkeit 0.0–1.0
        total_return_pct  (float) – Portfolio-Rendite in % (negativ = Verlust)
        total_value       (float) – Aktueller Portfolio-Gesamtwert in EUR
        force_random      (bool)  – True: erzwingt den Zufalls-Egg (zum Testen)
        random_seed       (int)   – Optional: setzt random.seed() für reproduzierbare Tests

    Sondermarker im Rückgabestring:
        CONFETTI_MARKER ("[KONFETTI]") – app.py soll st.balloons() aufrufen

    Returns:
        str mit Easter-Egg-Text, oder None wenn nichts ausgelöst wurde.
    """
    if context.get("random_seed") is not None:
        random.seed(context["random_seed"])

    candidates: list[tuple[int, str]] = []   # (Priorität, Text)

    # --- Budget > 1 Lambo ---
    total_value = context.get("total_value")
    if total_value is not None and total_value >= LAMBO_PRICE_EUR:
        lambos = total_value / LAMBO_PRICE_EUR
        candidates.append((
            _PRIORITY_LAMBO,
            (
                f"🏎️ **Herzlichen Glückwunsch!** "
                f"Du kannst dir jetzt einen Lambo leisten!\n\n"
                f"Dein Portfolio ist aktuell **{lambos:.4f} Lamborghini Aventador SVJ** wert. "
                f"Bestellformular liegt im Handschuhfach."
            ),
        ))

    # --- 100 Zyklen Meilenstein ---
    cycles          = context.get("cycles")
    previous_cycles = context.get("previous_cycles", 0)
    if (
        cycles is not None
        and cycles >= 100
        and previous_cycles < 100
    ):
        candidates.append((
            _PRIORITY_100CYC,
            (
                f"🏆 **100 Zyklen! Du bist jetzt offiziell ein Quant.** {CONFETTI_MARKER}\n\n"
                "Ernsthaft: 100 Trainingszyklen. Das ist Hingabe.\n"
                "Renaissance Technologies wird nervös. 📊"
            ),
        ))

    # --- Accuracy > 70% ---
    accuracy = context.get("accuracy")
    if accuracy is not None and accuracy > 0.70:
        candidates.append((
            _PRIORITY_AI_WALL,
            (
                f"🧠 **Achtung: KI übernimmt bald Wall Street.**\n\n"
                f"Aktuelle Modell-Genauigkeit: **{accuracy:.1%}** – Das ist bemerkenswert gut.\n"
                "Bitte nicht mit echtem Geld testen. Aber falls doch: Wir haben nichts gesagt."
            ),
        ))

    # --- Portfolio -50% ---
    total_return_pct = context.get("total_return_pct")
    if total_return_pct is not None and total_return_pct <= -50.0:
        candidates.append((
            _PRIORITY_BUST,
            (
                f"📉 **Even Warren Buffett hatte schlechte Tage…**\n\n"
                f"Aktueller Drawdown: **{total_return_pct:.1f}%**\n"
                "Berkshire Hathaway verlor 1999 rund 20%. Er kaufte trotzdem weiter.\n"
                "Das hier ist Paper-Trading. Kein echtes Geld. Tief durchatmen. 🧘"
            ),
        ))

    # --- Zufalls-Egg (~1% Chance) ---
    force_random = context.get("force_random", False)
    if force_random or random.random() < 0.01:
        candidates.append((
            _PRIORITY_RANDOM,
            "🎰 **Der Markt ist ein Casino – aber wenigstens kostenlos hier!**\n\n"
            "Fun Fact: Ein zufälliger Dart-werfender Affe schlägt die Mehrheit der "
            "Fondsmanager über 10 Jahre. Deine KI ist vermutlich besser als ein Affe. "
            "Wahrscheinlich.",
        ))

    if not candidates:
        return None

    # Höchste Priorität gewinnt (niedrigste Zahl)
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ===========================================================================
# Weitere kontextuelle Easter Eggs (für direkte Abfrage)
# ===========================================================================

def get_streak_egg(correct_streak: int) -> Optional[str]:
    """
    Gibt ein Easter Egg für eine Vorhersage-Serie zurück.
    correct_streak: Anzahl aufeinanderfolgend korrekte Vorhersagen.
    """
    if correct_streak >= 10:
        return (
            f"🔮 **{correct_streak} korrekte Vorhersagen in Folge!**\n"
            "Entweder ist dein Modell überragend oder die Märkte gerade sehr vorhersehbar.\n"
            "Oder beides. Genieße es, solange es anhält."
        )
    if correct_streak >= 5:
        return (
            f"⚡ **{correct_streak} in Folge richtig!** Nicht schlecht, Padawan."
        )
    return None


def get_trade_count_egg(num_trades: int) -> Optional[str]:
    """Easter Eggs für Trade-Meilensteine."""
    milestones = {
        1:   "🎉 **Erster Trade!** Der erste Schritt auf dem Weg zum Quant.",
        10:  "📊 **10 Trades!** Du weißt jetzt, wie man eine Order platziert.",
        50:  "💼 **50 Trades!** Das nächste Level: Steuerberater finden.",
        100: "🏆 **100 Trades!** Offiziell erfahrener Paper-Trader.",
        500: "🤖 **500 Trades!** Das Modell handelt schneller als du denken kannst.",
    }
    return milestones.get(num_trades)


# ===========================================================================
# Backward-Kompatibilität (app.py, ui_components.py)
# ===========================================================================

@dataclass
class EasterEgg:
    id:      str
    title:   str
    message: str
    emoji:   str = "🥚"


EASTER_EGGS: list[EasterEgg] = [
    EasterEgg(
        id="moon", title="🚀 To the Moon!", emoji="🚀",
        message=(
            "Das Modell sagt: 📈📈📈\n"
            "Aber vergiss nicht: Was rauf geht, kann auch runterkommen. "
            "Anlageberatung? Nein. Entertainmentwert? Definitiv."
        ),
    ),
    EasterEgg(
        id="dip", title="Buy the Dip™", emoji="🛒",
        message=(
            "Der Kurs ist gefallen. Die KI sieht eine Chance.\n"
            "Oder eine Falle. Wer weiß das schon? 🎰\n"
            "Disclaimer: StockMind haftet nicht für verlorene Lambos."
        ),
    ),
    EasterEgg(
        id="diamond_hands", title="💎 Diamond Hands erkannt!", emoji="💎",
        message=(
            "Du hältst diese Aktie schon sehr lange.\n"
            "Entweder bist du ein Genie oder ein geduldiger Mensch. "
            "Beides ist respektabel. 💎🙌"
        ),
    ),
    EasterEgg(
        id="yolo", title="YOLO-Modus aktiviert", emoji="🎲",
        message=(
            "Du hast 100% deines Portfolios in eine Aktie gesteckt.\n"
            "Mutig. Sehr mutig. 🎲\n"
            "Fun Fact: Diversifikation existiert aus einem Grund."
        ),
    ),
    EasterEgg(
        id="patience", title="🧘 Zen-Investor", emoji="🧘",
        message=(
            "Du hast heute keine einzige Order ausgeführt.\n"
            "Manchmal ist Nichtstun die beste Strategie. 🧘\n"
            "Warren Buffett würde stolz sein."
        ),
    ),
    EasterEgg(
        id="first_profit", title="🎉 Erster Gewinn!", emoji="🎉",
        message=(
            "Dein erster realisierter Gewinn! 🎊\n"
            f"Das ist erst der Anfang. Der Lambo ist jetzt "
            f"{LAMBO_PRICE_EUR/1000:.0f}k€ entfernt... aber du bist unterwegs!"
        ),
    ),
    EasterEgg(
        id="ten_trades", title="📊 Erfahrener Trader", emoji="📊",
        message=(
            "10 Trades abgeschlossen!\n"
            "Du hast genug Erfahrung, um zu wissen, dass Märkte unvorhersehbar sind. "
            "Oder? 😄"
        ),
    ),
]

EGG_LOOKUP = {egg.id: egg for egg in EASTER_EGGS}


def check_triggers(
    total_value:       float,
    total_return_pct:  float,
    num_trades:        int,
    positions:         list[dict],
    previous_value:    float = 0.0,
) -> list[EasterEgg]:
    """
    Prüft auf Easter-Egg-Bedingungen (Legacy-API für app.py).
    Gibt ausgelöste EasterEgg-Objekte zurück.
    """
    triggered: list[EasterEgg] = []

    if total_return_pct >= 20:
        triggered.append(EGG_LOOKUP["moon"])

    if total_return_pct <= -10:
        triggered.append(EGG_LOOKUP["dip"])

    if (previous_value > 0
            and previous_value < 10_000
            and total_value >= 10_000):
        triggered.append(EGG_LOOKUP["first_profit"])

    if (len(positions) == 1
            and positions[0].get("value", 0) / max(total_value, 1) > 0.95):
        triggered.append(EGG_LOOKUP["yolo"])

    if num_trades == 10:
        triggered.append(EGG_LOOKUP["ten_trades"])

    return triggered


# ---------------------------------------------------------------------------
# Lambo-Hilfsfunktionen (Compat: ui_components.py, app.py)
# ---------------------------------------------------------------------------

def eur_to_lambo(eur: float) -> float:
    return eur / LAMBO_PRICE_EUR


def lambo_to_eur(lambos: float) -> float:
    return lambos * LAMBO_PRICE_EUR


def format_lambo(eur: float) -> str:
    lambos = eur_to_lambo(eur)
    if lambos >= 1:
        return f"**{lambos:.2f} 🏎️ Lambos**"
    if lambos >= 0.01:
        return f"**{lambos:.4f} 🏎️ Lambos** ({lambos * 100:.2f}% eines Lambos)"
    return f"**{lambos:.6f} 🏎️ Lambos** (noch ein weiter Weg...)"


def lambo_progress_bar(eur: float) -> tuple[float, str]:
    pct = min(100.0, eur / LAMBO_PRICE_EUR * 100)
    if pct >= 100:  msg = "🏎️ LAMBO ACHIEVED! Herzlichen Glückwunsch!"
    elif pct >= 75: msg = "🔥 Fast da! Die Schlüssel warten schon..."
    elif pct >= 50: msg = "💪 Halbzeit! Bleib dabei!"
    elif pct >= 25: msg = "📈 Gut unterwegs! Weiter so!"
    elif pct >= 10: msg = "🌱 Anfänge sind gut! Geduld zahlt sich aus."
    else:           msg = "🐣 Jede Reise beginnt mit dem ersten Schritt."
    return pct, msg


# ---------------------------------------------------------------------------
# Zufällige Motivationsnachrichten
# ---------------------------------------------------------------------------

MOTIVATIONS: list[str] = [
    "📊 Daten lügen nicht. Menschen interpretieren sie falsch.",
    "💡 Tipp: Vergangenheit ist kein Indikator für die Zukunft – ignorieren wäre trotzdem dumm.",
    "🤖 Die KI analysiert. Du entscheidest. Gemeinsam vielleicht klüger.",
    "⚠️ Keine Anlageberatung. Ernstlich.",
    "🏎️ Jeden Tag ein Stück näher am Lambo... oder auch nicht.",
    "📉 Buy high, sell low – niemand will das, aber viele tun es.",
    "🧠 StockMind denkt mit. Aber dein Geld, deine Entscheidung.",
    "📅 Märkte sind langfristig aufwärts gerichtet. Kurzfristig: Chaos.",
    "🎯 Ein gutes Modell ist ein bescheidenes Modell.",
    "🦆 Wenn du nicht weißt was du tust, tu es langsam.",
    "📚 Peter Lynch: 'Investiere nur in Dinge, die du verstehst.' Viel Erfolg bei Derivaten.",
    "🌊 Der Markt kann länger irrational bleiben als du solvent.",
]


def random_motivation() -> str:
    return random.choice(MOTIVATIONS)
