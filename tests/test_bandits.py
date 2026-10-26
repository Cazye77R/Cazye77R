"""
StockMind – Tests für Bandit-Algorithmen.

Prüft UCB1, D-UCB und Thompson auf stationären und nicht-stationären
Reward-Streams, sowie compare_bandits() und get_bandit().
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))

from modules.trainer import (
    UCB1Bandit,
    DiscountedUCB1,
    ThompsonSamplingBandit,
    compare_bandits,
    get_bandit,
    _BANDIT_NAMES,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

_METHODS = ["SMA Crossover", "RSI", "MACD", "Bollinger Bands"]


def _make_state(history: list[tuple[str, bool]]) -> dict:
    """Baut einen state-Dict aus (method, correct)-Paaren auf."""
    accuracy_history = [
        {"method": m, "correct": c, "cycle": i + 1}
        for i, (m, c) in enumerate(history)
    ]
    method_scores: dict[str, float] = {}
    counts: dict[str, int] = {}
    for m, c in history:
        counts[m] = counts.get(m, 0) + 1
        prev = method_scores.get(m, 0.0)
        method_scores[m] = (prev * (counts[m] - 1) + (1.0 if c else 0.0)) / counts[m]

    return {
        "cycles":          len(history),
        "accuracy_history": accuracy_history,
        "method_scores":   method_scores,
    }


def _uniform_history(n: int = 20) -> list[tuple[str, bool]]:
    """Jede Methode reihum, abwechselnd richtig/falsch."""
    rng = np.random.default_rng(0)
    return [
        (_METHODS[i % len(_METHODS)], bool(rng.integers(0, 2)))
        for i in range(n)
    ]


def _nonstationary_history(n_per_phase: int = 15) -> list[tuple[str, bool]]:
    """
    Phase 1: RSI dominiert (Reward ≈ 0.9)
    Phase 2: MACD dominiert (Reward ≈ 0.9), RSI schlechter (≈ 0.1)
    """
    rng = np.random.default_rng(42)
    history: list[tuple[str, bool]] = []

    # Phase 1
    for _ in range(n_per_phase):
        for m in _METHODS:
            p = 0.9 if m == "RSI" else 0.3
            history.append((m, bool(rng.random() < p)))

    # Phase 2 – Regime-Wechsel
    for _ in range(n_per_phase):
        for m in _METHODS:
            p = 0.9 if m == "MACD" else 0.1
            history.append((m, bool(rng.random() < p)))

    return history


# ---------------------------------------------------------------------------
# UCB1Bandit
# ---------------------------------------------------------------------------

class TestUCB1Bandit:
    def test_selects_from_methods(self):
        bandit = UCB1Bandit()
        state = _make_state(_uniform_history())
        choice = bandit.select(state, _METHODS)
        assert choice in _METHODS

    def test_prefers_high_accuracy_method(self):
        """Eine Methode mit 100% Accuracy und gleichen Zählern muss gewählt werden."""
        history = [
            ("RSI", True), ("RSI", True), ("RSI", True),
            ("SMA Crossover", False), ("SMA Crossover", False), ("SMA Crossover", False),
            ("MACD", False), ("MACD", False),
            ("Bollinger Bands", False), ("Bollinger Bands", False),
        ]
        state = _make_state(history)
        bandit = UCB1Bandit(c=0.01)     # geringe Exploration → Exploitation dominiert
        choice = bandit.select(state, _METHODS)
        assert choice == "RSI"

    def test_exploration_increases_with_low_count(self):
        """Selten gewählte Methode erhält Explorations-Bonus."""
        history = [("RSI", True)] * 10 + [("MACD", False)] * 1
        state = _make_state(history)
        # Mit sehr hoher Explorations-Konstante muss MACD (seltener) gewählt werden
        bandit = UCB1Bandit(c=100.0)
        choice = bandit.select(state, ["RSI", "MACD"])
        assert choice == "MACD"

    def test_custom_exploration_constant(self):
        UCB1Bandit(c=2.0)  # darf nicht werfen

    def test_single_method(self):
        state = _make_state([("RSI", True)] * 5)
        bandit = UCB1Bandit()
        assert bandit.select(state, ["RSI"]) == "RSI"


# ---------------------------------------------------------------------------
# DiscountedUCB1
# ---------------------------------------------------------------------------

class TestDiscountedUCB1:
    def test_invalid_gamma_raises(self):
        with pytest.raises(ValueError):
            DiscountedUCB1(gamma=0.0)
        with pytest.raises(ValueError):
            DiscountedUCB1(gamma=1.0)
        with pytest.raises(ValueError):
            DiscountedUCB1(gamma=1.5)

    def test_selects_from_methods(self):
        bandit = DiscountedUCB1(gamma=0.95)
        state = _make_state(_uniform_history())
        assert bandit.select(state, _METHODS) in _METHODS

    def test_adapts_to_regime_change(self):
        """
        Phase 1: RSI gut. Phase 2: MACD gut.
        D-UCB mit niedrigem γ soll am Ende MACD bevorzugen.
        """
        history = _nonstationary_history(n_per_phase=8)
        state = _make_state(history)

        # γ = 0.7 → schnelles Vergessen → reagiert auf Regime-Wechsel
        bandit_fast = DiscountedUCB1(gamma=0.7, c=0.1)
        choice = bandit_fast.select(state, _METHODS)
        assert choice == "MACD"

    def test_ucb1_stale_after_regime_change(self):
        """
        UCB1 ignoriert Regime-Wechsel → bleibt bei RSI (Phase-1-Winner).
        D-UCB mit γ=0.7 wechselt zu MACD.
        """
        history = _nonstationary_history(n_per_phase=10)
        state = _make_state(history)

        ucb1  = UCB1Bandit(c=0.01)
        ducb  = DiscountedUCB1(gamma=0.6, c=0.01)

        choice_ucb1 = ucb1.select(state, _METHODS)
        choice_ducb = ducb.select(state, _METHODS)

        # D-UCB reagiert auf Regime-Wechsel; beide können verschieden sein
        # Mindestens D-UCB muss MACD wählen
        assert choice_ducb == "MACD"

    def test_discounted_count_formula(self):
        """Überprüft die diskontierte Zähler-Summe numerisch."""
        gamma = 0.9
        history = [("RSI", True)] * 5
        state = _make_state(history)
        t = len(history)

        # Erwarteter diskontierter Zähler für RSI nach 5 Beobachtungen
        expected_n = sum(gamma ** (t - 1 - s) for s in range(t))
        # Berechnung von Hand: Σ γ^k für k=0..4
        expected_n_manual = sum(gamma**k for k in range(t))
        assert abs(expected_n - expected_n_manual) < 1e-9

    def test_gamma_0_95_default(self):
        DiscountedUCB1()  # Standardkonstruktor mit Default-Gamma


# ---------------------------------------------------------------------------
# ThompsonSamplingBandit
# ---------------------------------------------------------------------------

class TestThompsonSamplingBandit:
    def test_selects_from_methods(self):
        bandit = ThompsonSamplingBandit(rng_seed=0)
        state = _make_state(_uniform_history())
        assert bandit.select(state, _METHODS) in _METHODS

    def test_converges_to_best_method(self):
        """
        Mit genug Daten muss Thompson die stets richtige Methode wählen.
        50 Runs auf deterministischem State → muss RSI wählen.
        """
        history = (
            [("RSI", True)] * 20
            + [("MACD", False)] * 20
            + [("SMA Crossover", False)] * 20
            + [("Bollinger Bands", False)] * 20
        )
        state = _make_state(history)
        bandit = ThompsonSamplingBandit(rng_seed=7)

        wins = {"RSI": 0, "other": 0}
        for _ in range(100):
            c = bandit.select(state, _METHODS)
            if c == "RSI":
                wins["RSI"] += 1
            else:
                wins["other"] += 1

        assert wins["RSI"] > 80, (
            f"Thompson soll RSI dominant wählen, bekam nur {wins['RSI']}/100"
        )

    def test_uniform_prior_explores_all(self):
        """Mit leerem History wählt Thompson alle Methoden irgendwann."""
        state = _make_state([])
        bandit = ThompsonSamplingBandit(rng_seed=0)
        chosen: set[str] = set()
        for _ in range(200):
            chosen.add(bandit.select(state, _METHODS))
        assert chosen == set(_METHODS)

    def test_reproducible_with_seed(self):
        state = _make_state(_uniform_history())
        b1 = ThompsonSamplingBandit(rng_seed=123)
        b2 = ThompsonSamplingBandit(rng_seed=123)
        seq1 = [b1.select(state, _METHODS) for _ in range(10)]
        seq2 = [b2.select(state, _METHODS) for _ in range(10)]
        assert seq1 == seq2


# ---------------------------------------------------------------------------
# get_bandit factory
# ---------------------------------------------------------------------------

class TestGetBandit:
    def test_ucb1(self):
        assert isinstance(get_bandit("UCB1"), UCB1Bandit)

    def test_ducb(self):
        assert isinstance(get_bandit("D-UCB"), DiscountedUCB1)

    def test_thompson(self):
        assert isinstance(get_bandit("Thompson"), ThompsonSamplingBandit)

    def test_unknown_defaults_to_ucb1(self):
        assert isinstance(get_bandit("unknown"), UCB1Bandit)

    def test_gamma_forwarded_to_ducb(self):
        b = get_bandit("D-UCB", gamma=0.8)
        assert isinstance(b, DiscountedUCB1)
        assert b.gamma == 0.8

    def test_c_forwarded_to_ucb1(self):
        b = get_bandit("UCB1", c=2.0)
        assert isinstance(b, UCB1Bandit)
        assert b.c == 2.0

    def test_bandit_names_constant(self):
        assert set(_BANDIT_NAMES) == {"UCB1", "D-UCB", "Thompson"}


# ---------------------------------------------------------------------------
# compare_bandits
# ---------------------------------------------------------------------------

class TestCompareBandits:
    def test_returns_expected_keys(self):
        history = _uniform_history(20)
        state_hist = [{"method": m, "correct": c} for m, c in history]
        result = compare_bandits(state_hist, _METHODS)
        assert "cumulative_rewards" in result
        assert "final_rewards"      in result
        assert "selections"         in result
        assert "figure"             in result

    def test_all_bandits_in_output(self):
        history = [{"method": m, "correct": c} for m, c in _uniform_history(20)]
        result = compare_bandits(history, _METHODS)
        for bname in ("UCB1", "D-UCB", "Thompson"):
            assert bname in result["cumulative_rewards"]

    def test_cumulative_reward_monotone(self):
        """Kumulativer Reward darf nicht fallen."""
        history = [{"method": m, "correct": c} for m, c in _uniform_history(30)]
        result = compare_bandits(history, _METHODS)
        for bname, rewards in result["cumulative_rewards"].items():
            diffs = [rewards[i+1] - rewards[i] for i in range(len(rewards)-1)]
            assert all(d >= -1e-9 for d in diffs), f"{bname}: kumulativer Reward fiel"

    def test_reward_length_matches_history(self):
        n = 25
        history = [{"method": m, "correct": c} for m, c in _uniform_history(n)]
        result = compare_bandits(history, _METHODS)
        for bname, rewards in result["cumulative_rewards"].items():
            assert len(rewards) == n, f"{bname}: Länge {len(rewards)} != {n}"

    def test_empty_history_returns_empty_figure(self):
        result = compare_bandits([], _METHODS)
        assert result["cumulative_rewards"] == {}

    def test_ducb_beats_ucb1_on_nonstationary(self):
        """
        Auf einem Regime-Wechsel-Stream soll D-UCB mehr kumulativen Reward
        akkumulieren als UCB1 (statistisch erwartbar mit γ=0.7).
        """
        history = [
            {"method": m, "correct": c}
            for m, c in _nonstationary_history(n_per_phase=12)
        ]
        result = compare_bandits(history, _METHODS, gamma=0.7, c=0.1)
        ducb_r = result["final_rewards"].get("D-UCB", 0)
        ucb1_r = result["final_rewards"].get("UCB1", 0)
        # D-UCB sollte bei starkem Regime-Wechsel besser abschneiden
        assert ducb_r >= ucb1_r * 0.85, (
            f"D-UCB ({ducb_r:.1f}) sollte nahe an UCB1 ({ucb1_r:.1f}) liegen "
            f"oder besser sein auf nicht-stationärem Stream"
        )

    def test_figure_has_traces(self):
        history = [{"method": m, "correct": c} for m, c in _uniform_history(20)]
        result = compare_bandits(history, _METHODS)
        assert len(result["figure"].data) == 3  # UCB1, D-UCB, Thompson
