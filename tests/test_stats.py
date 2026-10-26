"""Tests für modules/stats.py (Wilson-Intervall + Mehrheits-Baseline)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stockmind"))

from modules.stats import (  # noqa: E402
    MIN_CYCLES_FOR_VERDICT,
    majority_baseline,
    summarize_accuracy,
    summarize_by_method,
    wilson_interval,
)


def _hist(pairs, method="RSI"):
    """pairs: [(correct, actual), ...]"""
    return [{"correct": c, "actual": a, "method": method} for c, a in pairs]


class TestWilson:
    def test_known_value(self):
        # Referenzwert: 8/10 bei 95 % -> ca. (0.490, 0.943)
        lo, hi = wilson_interval(8, 10)
        assert lo == pytest.approx(0.490, abs=0.002)
        assert hi == pytest.approx(0.943, abs=0.002)

    def test_no_data_is_fully_uncertain(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_extremes_stay_within_unit_interval(self):
        lo0, hi0 = wilson_interval(0, 20)
        lo1, hi1 = wilson_interval(20, 20)
        assert lo0 == 0.0 and 0 < hi0 < 0.2
        assert hi1 == 1.0 and 0.8 < lo1 < 1

    def test_interval_narrows_with_more_data(self):
        lo_s, hi_s = wilson_interval(6, 10)
        lo_l, hi_l = wilson_interval(600, 1000)
        assert (hi_l - lo_l) < (hi_s - lo_s)

    def test_contains_point_estimate(self):
        for k, n in [(1, 7), (5, 9), (13, 40)]:
            lo, hi = wilson_interval(k, n)
            assert lo <= k / n <= hi

    @pytest.mark.parametrize("k,n", [(-1, 5), (6, 5)])
    def test_invalid_counts_raise(self, k, n):
        with pytest.raises(ValueError):
            wilson_interval(k, n)


class TestBaseline:
    def test_majority(self):
        assert majority_baseline(["UP", "UP", "DOWN", "UP"]) == ("UP", 0.75)

    def test_empty(self):
        assert majority_baseline([]) == ("–", 0.0)


class TestSummarize:
    def test_ignores_ml_entries_without_actual_or_correct(self):
        hist = _hist([(True, "UP")] * 3) + [
            {"correct": None, "method": "sklearn/GBM"},
            {"method": "RSI"},
        ]
        s = summarize_accuracy(hist)
        assert s.n == 3 and s.correct == 3

    def test_too_few_cycles_gives_no_verdict(self):
        s = summarize_accuracy(_hist([(True, "UP")] * (MIN_CYCLES_FOR_VERDICT - 1)))
        assert s.verdict == "zu_wenig_daten"

    def test_clearly_better_than_baseline(self):
        # Markt 50/50 -> Baseline 0.5; Modell trifft 38/40
        hist = _hist([(True, "UP")] * 19 + [(True, "DOWN")] * 19 + [(False, "UP")] * 2)
        s = summarize_accuracy(hist)
        assert s.verdict == "besser"

    def test_lucky_streak_is_not_significant(self):
        # 7/10 klingt gut, ist bei n=10 aber nicht von 50 % trennbar
        hist = _hist([(True, "UP")] * 4 + [(True, "DOWN")] * 3 + [(False, "UP")] * 3)
        s = summarize_accuracy(hist)
        assert s.verdict == "unklar"

    def test_worse_than_baseline(self):
        # Markt steigt fast immer, Modell liegt fast immer falsch
        hist = _hist([(False, "UP")] * 38 + [(True, "UP")] * 2)
        assert summarize_accuracy(hist).verdict == "schlechter"

    def test_by_method_splits(self):
        hist = _hist([(True, "UP")] * 5, "RSI") + _hist([(False, "UP")] * 4, "MACD")
        out = summarize_by_method(hist)
        assert out["RSI"].n == 5 and out["MACD"].n == 4
        assert out["RSI"].accuracy == 1.0 and out["MACD"].accuracy == 0.0
