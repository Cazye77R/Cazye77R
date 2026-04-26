"""
StockMind – Tests für get_data_quality_report() und yfinance-Parameter.

Prüft:
- Rückgabe-Struktur und Feldtypen
- Erkennung von fehlenden Handelstagen
- Erkennung von Zero-Volume-Tagen
- Erkennung großer Tagesbewegungen (Outlier)
- Grenzfälle (leerer DataFrame, einzelne Zeile)
- back_adjust-Parameter in den yfinance-Hilfsfunktionen
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))

from modules.data_fetcher import get_data_quality_report


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_df(
    start: str = "2024-01-02",
    n_days: int = 20,
    include_weekends: bool = False,
    volume: float | None = 1_000_000.0,
    price_seq: list[float] | None = None,
) -> pd.DataFrame:
    """Erstellt minimalen OHLCV-DataFrame für Tests."""
    if include_weekends:
        dates = pd.date_range(start, periods=n_days, freq="D")
    else:
        dates = pd.date_range(start, periods=n_days, freq="B")  # Wochentage

    if price_seq is not None:
        closes = np.array(price_seq[:n_days], dtype=float)
    else:
        rng = np.random.default_rng(0)
        closes = 100.0 + rng.normal(0, 1, n_days).cumsum()

    df = pd.DataFrame(
        {
            "Open":   closes,
            "High":   closes * 1.005,
            "Low":    closes * 0.995,
            "Close":  closes,
            "Volume": volume if volume is not None else 0.0,
        },
        index=pd.DatetimeIndex(dates),
    )
    return df


# ---------------------------------------------------------------------------
# Rückgabe-Struktur
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_required_keys_present(self):
        df = _make_df()
        report = get_data_quality_report(df)
        for key in ("missing_days", "zero_volume_days", "max_daily_move_pct",
                    "first_date", "last_date", "issues", "ok"):
            assert key in report, f"Schlüssel '{key}' fehlt"

    def test_field_types(self):
        df = _make_df()
        r = get_data_quality_report(df)
        assert isinstance(r["missing_days"],        int)
        assert isinstance(r["zero_volume_days"],    int)
        assert isinstance(r["max_daily_move_pct"],  float)
        assert isinstance(r["first_date"],          str)
        assert isinstance(r["last_date"],           str)
        assert isinstance(r["issues"],              list)
        assert isinstance(r["ok"],                  bool)

    def test_dates_are_iso_format(self):
        df = _make_df(start="2024-03-11", n_days=10)
        r = get_data_quality_report(df)
        date.fromisoformat(r["first_date"])  # wirft ValueError wenn kein ISO
        date.fromisoformat(r["last_date"])

    def test_first_date_before_last_date(self):
        df = _make_df(n_days=10)
        r = get_data_quality_report(df)
        assert r["first_date"] <= r["last_date"]


# ---------------------------------------------------------------------------
# Leerer / trivialer DataFrame
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_dataframe(self):
        r = get_data_quality_report(pd.DataFrame())
        assert r["ok"] is False
        assert r["issues"]

    def test_none_input(self):
        r = get_data_quality_report(None)  # type: ignore[arg-type]
        assert r["ok"] is False

    def test_single_row(self):
        df = _make_df(n_days=1)
        r = get_data_quality_report(df)
        # Kein Crash, max_daily_move_pct = 0 (nur eine Zeile)
        assert r["max_daily_move_pct"] == 0.0

    def test_two_rows_no_issues(self):
        df = _make_df(n_days=2, price_seq=[100.0, 101.0])
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 0
        assert r["max_daily_move_pct"] == pytest.approx(1.0, rel=0.01)


# ---------------------------------------------------------------------------
# Fehlende Handelstage
# ---------------------------------------------------------------------------

class TestMissingDays:
    def test_no_missing_days_for_complete_series(self):
        """20 aufeinanderfolgende Wochentage → keine fehlenden Tage."""
        df = _make_df(n_days=20)
        r = get_data_quality_report(df)
        assert r["missing_days"] == 0

    def test_detects_gap_in_series(self):
        """Lücke von mehreren Wochentagen → missing_days > 0."""
        # dates_a endet Fr 2024-01-05; dates_b beginnt Mo 2024-01-22
        # → 10 fehlende Wochentage (Jan 8–19)
        dates_a = pd.bdate_range("2024-01-02", periods=5)
        dates_b = pd.bdate_range("2024-01-22", periods=5)
        dates = list(dates_a) + list(dates_b)
        closes = np.array([100.0] * len(dates))
        df = pd.DataFrame(
            {"Open": closes, "High": closes * 1.005, "Low": closes * 0.995,
             "Close": closes, "Volume": 1e6},
            index=pd.DatetimeIndex(dates),
        )
        r = get_data_quality_report(df)
        # Jan 8–19 = 10 Wochentage fehlen (inkl. Martin Luther King Day 15. Jan)
        assert r["missing_days"] >= 9

    def test_missing_days_count_is_int(self):
        df = _make_df(n_days=5)
        r = get_data_quality_report(df)
        assert isinstance(r["missing_days"], int)


# ---------------------------------------------------------------------------
# Zero-Volume-Tage
# ---------------------------------------------------------------------------

class TestZeroVolume:
    def test_no_zero_volume(self):
        df = _make_df(n_days=10, volume=500_000.0)
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 0
        assert r["ok"] is True

    def test_all_zero_volume(self):
        df = _make_df(n_days=5, volume=0.0)
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 5
        assert r["ok"] is False

    def test_partial_zero_volume(self):
        df = _make_df(n_days=6, volume=1_000.0)
        df.loc[df.index[0], "Volume"] = 0.0
        df.loc[df.index[3], "Volume"] = 0.0
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 2

    def test_nan_volume_counts_as_zero(self):
        df = _make_df(n_days=4, volume=1_000.0)
        df.loc[df.index[1], "Volume"] = float("nan")
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 1

    def test_missing_volume_column(self):
        df = _make_df(n_days=5)
        df = df.drop(columns=["Volume"])
        r = get_data_quality_report(df)
        assert r["zero_volume_days"] == 0   # kein Fehler, kein False-Positive


# ---------------------------------------------------------------------------
# Maximale Tagesbewegung (Outlier)
# ---------------------------------------------------------------------------

class TestMaxDailyMove:
    def test_normal_moves_no_warning(self):
        """Bewegungen < 20 % → ok."""
        prices = [100.0, 102.0, 101.5, 103.0, 102.5]
        df = _make_df(n_days=5, price_seq=prices)
        r = get_data_quality_report(df)
        assert r["max_daily_move_pct"] < 20.0
        assert r["ok"] is True

    def test_large_move_triggers_warning(self):
        """Bewegung von 50 % → Warning in issues."""
        prices = [100.0, 150.0, 151.0, 150.5]
        df = _make_df(n_days=4, price_seq=prices)
        r = get_data_quality_report(df)
        assert r["max_daily_move_pct"] == pytest.approx(50.0, rel=0.01)
        assert r["ok"] is False
        assert any("Tagesbewegung" in iss or "Split" in iss for iss in r["issues"])

    def test_max_move_exact_threshold_no_warning(self):
        """Genau 20 % → kein Warning (nur > 20 % löst aus)."""
        prices = [100.0, 120.0, 121.0]
        df = _make_df(n_days=3, price_seq=prices)
        r = get_data_quality_report(df)
        assert r["max_daily_move_pct"] == pytest.approx(20.0, rel=0.01)
        # Genau 20 % liegt an der Grenze – kein Warning erwartet
        assert not any("Tagesbewegung" in iss for iss in r["issues"])

    def test_max_move_just_above_threshold(self):
        """20.1 % → Warning."""
        prices = [100.0, 120.1, 121.0]
        df = _make_df(n_days=3, price_seq=prices)
        r = get_data_quality_report(df)
        assert r["max_daily_move_pct"] > 20.0
        assert any("Tagesbewegung" in iss for iss in r["issues"])


# ---------------------------------------------------------------------------
# ok-Flag
# ---------------------------------------------------------------------------

class TestOkFlag:
    def test_ok_true_for_clean_data(self):
        df = _make_df(n_days=10, volume=1_000_000.0,
                      price_seq=list(range(100, 110)))
        r = get_data_quality_report(df)
        assert r["ok"] is True
        assert r["issues"] == []

    def test_ok_false_when_any_issue(self):
        df = _make_df(n_days=3, volume=0.0)
        r = get_data_quality_report(df)
        assert r["ok"] is False
        assert len(r["issues"]) >= 1

    def test_ok_matches_empty_issues(self):
        df = _make_df(n_days=10)
        r = get_data_quality_report(df)
        assert r["ok"] == (len(r["issues"]) == 0)


# ---------------------------------------------------------------------------
# yfinance back_adjust-Parameter im Quellcode
# ---------------------------------------------------------------------------

class TestYfinanceParameters:
    """Smoke-Tests: prüfen ob back_adjust=False im Quellcode steht."""

    def test_back_adjust_false_in_history(self):
        import inspect
        from modules import data_fetcher
        src = inspect.getsource(data_fetcher._fetch_yf_history)
        assert "back_adjust=False" in src, (
            "_fetch_yf_history muss back_adjust=False enthalten"
        )

    def test_back_adjust_false_in_download(self):
        import inspect
        from modules import data_fetcher
        src = inspect.getsource(data_fetcher._fetch_yf_download)
        assert "back_adjust=False" in src, (
            "_fetch_yf_download muss back_adjust=False enthalten"
        )

    def test_auto_adjust_true_in_history(self):
        import inspect
        from modules import data_fetcher
        src = inspect.getsource(data_fetcher._fetch_yf_history)
        assert "auto_adjust=True" in src

    def test_auto_adjust_true_in_download(self):
        import inspect
        from modules import data_fetcher
        src = inspect.getsource(data_fetcher._fetch_yf_download)
        assert "auto_adjust=True" in src
