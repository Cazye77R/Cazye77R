"""
StockMind – einfache Statistik für die Trefferquote der LLM-Trainingszyklen.

Eine einzelne Prozentzahl wie "64 % Accuracy" nach 20 Zyklen sagt wenig aus:
bei so wenigen Stichproben ist die Unsicherheit groß, und ohne Vergleichswert
ist nicht klar, ob 64 % überhaupt gut sind (bei einem steigenden Markt trifft
"immer UP" schon oft über 50 %). Dieses Modul liefert deshalb

- ein Wilson-Konfidenzintervall für die Trefferquote und
- eine Mehrheits-Baseline ("immer die häufigste tatsächliche Richtung raten").

Alles hier sind reine Funktionen ohne Streamlit-/IO-Abhängigkeit.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

# Ab dieser Zyklenzahl wird überhaupt ein Urteil gefällt.
MIN_CYCLES_FOR_VERDICT = 10


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson-Score-Intervall für eine Binomial-Trefferquote (Standard: 95 %).

    Robuster als die Normal-Näherung bei kleinen n und Quoten nahe 0/1.
    Für n == 0 ist nichts bekannt: (0.0, 1.0).
    """
    if n <= 0:
        return 0.0, 1.0
    if not 0 <= successes <= n:
        raise ValueError(f"successes muss in [0, n] liegen, nicht {successes} (n={n}).")
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def majority_baseline(actuals: list[str]) -> tuple[str, float]:
    """
    Trefferquote der Strategie "immer die häufigste tatsächliche Richtung".

    Hinweis: Die häufigste Richtung ist erst im Nachhinein bekannt – die
    Baseline ist also eine (bewusst strenge) Hindsight-Latte, kein handelbarer
    Vergleich. Leere Eingabe: ("–", 0.0).
    """
    if not actuals:
        return "–", 0.0
    label, count = Counter(actuals).most_common(1)[0]
    return label, count / len(actuals)


@dataclass(frozen=True)
class AccuracySummary:
    n: int
    correct: int
    accuracy: float
    ci_low: float
    ci_high: float
    baseline_label: str
    baseline_accuracy: float
    verdict: str  # "zu_wenig_daten" | "besser" | "schlechter" | "unklar"


def summarize_accuracy(history: list[dict]) -> AccuracySummary:
    """
    Fasst accuracy_history-Einträge zusammen.

    Berücksichtigt nur Einträge mit gültigem ``correct`` (bool) und ``actual``;
    ML-Trainingseinträge (``correct=None``) werden ignoriert.
    """
    rows = [
        e
        for e in history
        if isinstance(e.get("correct"), bool) and isinstance(e.get("actual"), str)
    ]
    n = len(rows)
    correct = sum(1 for e in rows if e["correct"])
    acc = correct / n if n else 0.0
    lo, hi = wilson_interval(correct, n)
    label, base = majority_baseline([e["actual"] for e in rows])

    if n < MIN_CYCLES_FOR_VERDICT:
        verdict = "zu_wenig_daten"
    elif lo > base:
        verdict = "besser"
    elif hi < base:
        verdict = "schlechter"
    else:
        verdict = "unklar"

    return AccuracySummary(n, correct, acc, lo, hi, label, base, verdict)


def summarize_by_method(history: list[dict]) -> dict[str, AccuracySummary]:
    """Wie summarize_accuracy, aber getrennt nach Analyse-Methode."""
    by_method: dict[str, list[dict]] = {}
    for e in history:
        m = e.get("method")
        if isinstance(m, str) and m:
            by_method.setdefault(m, []).append(e)
    return {m: summarize_accuracy(rows) for m, rows in by_method.items()}


VERDICT_TEXT = {
    "zu_wenig_daten": (
        f"Zu wenige Zyklen (< {MIN_CYCLES_FOR_VERDICT}) für eine belastbare Aussage."
    ),
    "besser": "Signifikant besser als die Mehrheits-Baseline.",
    "schlechter": "Signifikant schlechter als die Mehrheits-Baseline.",
    "unklar": "Statistisch nicht von der Mehrheits-Baseline unterscheidbar.",
}
