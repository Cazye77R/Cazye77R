"""
StockMind – Tests für compute_metrics, walk_forward_backtest und compute_slippage.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))

from modules.backtester import BacktestResult, backtest_signals, compute_metrics, compute_slippage
from modules.walk_forward import walk_forward_backtest


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _equity_curve(n: int = 252, start: float = 10_000.0, drift: float = 0.001) -> pd.Series:
    """Monoton ansteigende Equity-Kurve (kein Drawdown)."""
    rng = np.random.default_rng(42)
    rets = drift + rng.normal(0, 0.005, n)
    eq = start * np.cumprod(1 + rets)
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.Series(eq, index=idx)


def _flat_equity(n: int = 252, value: float = 10_000.0) -> pd.Series:
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.Series(np.full(n, value), index=idx)


def _drawdown_equity() -> pd.Series:
    """Equity: steigt auf 12k, fällt auf 9k → 25% Drawdown."""
    vals = [10_000] * 50 + [12_000] * 50 + [9_000] * 50
    idx = pd.date_range("2023-01-02", periods=150, freq="B")
    return pd.Series(vals, dtype=float, index=idx)


def _make_trades(n_wins: int = 5, n_losses: int = 3) -> pd.DataFrame:
    rows = []
    for i in range(n_wins):
        rows.append({
            "date": f"2023-{i+1:02d}-10", "action": "BUY", "price": 100.0, "shares": 10,
        })
        rows.append({
            "date": f"2023-{i+1:02d}-20", "action": "SELL", "price": 110.0,
            "shares": 10, "pnl": 100.0,
        })
    for i in range(n_losses):
        j = n_wins + i
        rows.append({
            "date": f"2023-{j+1:02d}-10", "action": "BUY", "price": 100.0, "shares": 10,
        })
        rows.append({
            "date": f"2023-{j+1:02d}-20", "action": "SELL", "price": 90.0,
            "shares": 10, "pnl": -100.0,
        })
    return pd.DataFrame(rows)


def _make_ohlcv(n: int = 500, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = base + np.cumsum(rng.normal(0, 1, n))
    close = np.clip(close, 1.0, None)
    high  = close * (1 + rng.uniform(0, 0.01, n))
    low   = close * (1 - rng.uniform(0, 0.01, n))
    vol   = rng.integers(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=pd.date_range("2021-01-04", periods=n, freq="B"),
    )


# ---------------------------------------------------------------------------
# compute_metrics – Grundfunktionen
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_empty_equity_returns_zero_dict(self):
        m = compute_metrics(pd.Series(dtype=float), pd.DataFrame())
        assert m["n_trades"] == 0
        assert m["total_return"] == 0.0

    def test_single_point_equity(self):
        m = compute_metrics(pd.Series([10_000.0]), pd.DataFrame())
        assert m["total_return"] == 0.0

    def test_total_return_positive(self):
        eq = pd.Series([10_000.0, 12_000.0])
        m = compute_metrics(eq, pd.DataFrame())
        assert abs(m["total_return"] - 20.0) < 0.01

    def test_total_return_negative(self):
        eq = pd.Series([10_000.0, 8_000.0])
        m = compute_metrics(eq, pd.DataFrame())
        assert abs(m["total_return"] - (-20.0)) < 0.01

    def test_max_drawdown_no_drawdown(self):
        eq = _equity_curve(100, drift=0.002)
        m = compute_metrics(eq, pd.DataFrame())
        # Mit positivem Drift und kleiner Volatilität bleibt DD nah bei 0
        assert m["max_drawdown"] <= 0

    def test_max_drawdown_known_value(self):
        eq = _drawdown_equity()
        m = compute_metrics(eq, pd.DataFrame())
        # 9000 / 12000 - 1 = -25%
        assert m["max_drawdown"] <= -20.0

    def test_sharpe_positive_drift(self):
        eq = _equity_curve(252, drift=0.001)
        m = compute_metrics(eq, pd.DataFrame())
        assert m["sharpe"] > 0

    def test_sharpe_flat_equity(self):
        """Flache Equity → std = 0 → Sharpe = 0 (kein NaN)."""
        m = compute_metrics(_flat_equity(), pd.DataFrame())
        assert m["sharpe"] == 0.0

    def test_sortino_non_negative_for_rising(self):
        eq = _equity_curve(252, drift=0.002)
        m = compute_metrics(eq, pd.DataFrame())
        assert m["sortino"] >= 0

    def test_calmar_ratio(self):
        """Calmar = CAGR / |MaxDD|; positiver Trend → Calmar > 0."""
        eq = _equity_curve(500, drift=0.001)
        m = compute_metrics(eq, pd.DataFrame())
        if m["max_drawdown"] < 0:
            assert m["calmar"] > 0

    def test_win_rate(self):
        trades = _make_trades(n_wins=7, n_losses=3)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert abs(m["win_rate"] - 70.0) < 0.01

    def test_profit_factor(self):
        """5 × 100€ Gewinn, 3 × 100€ Verlust → PF = 500/300 ≈ 1.667."""
        trades = _make_trades(n_wins=5, n_losses=3)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert abs(m["profit_factor"] - 5.0 / 3.0) < 0.01

    def test_expectancy(self):
        """(5 × 100 + 3 × -100) / 8 = 25.0 €."""
        trades = _make_trades(n_wins=5, n_losses=3)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert abs(m["expectancy"] - 25.0) < 0.01

    def test_payoff_ratio(self):
        """Alle Wins +100, alle Losses -100 → Payoff = 1.0."""
        trades = _make_trades(n_wins=4, n_losses=4)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert abs(m["payoff_ratio"] - 1.0) < 0.01

    def test_max_consecutive_losses(self):
        rows = []
        # 3 Verluste in Folge, dann 1 Gewinn, dann 2 Verluste
        pnl_seq = [-1, -1, -1, 1, -1, -1]
        for i, pnl in enumerate(pnl_seq):
            rows.append({"date": "2023-01-01", "action": "BUY", "price": 100.0, "shares": 1})
            rows.append({"date": "2023-01-02", "action": "SELL", "price": 100.0,
                          "shares": 1, "pnl": float(pnl)})
        trades = pd.DataFrame(rows)
        eq = _equity_curve(50)
        m = compute_metrics(eq, trades)
        assert m["max_consecutive_losses"] == 3

    def test_n_trades_count(self):
        trades = _make_trades(n_wins=4, n_losses=2)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert m["n_trades"] == 6

    def test_avg_trade_duration(self):
        """Jeder Trade dauert 10 Tage (Buy am 10., Sell am 20.)."""
        trades = _make_trades(n_wins=3, n_losses=0)
        eq = _equity_curve(200)
        m = compute_metrics(eq, trades)
        assert m["avg_trade_duration_days"] == 10

    def test_cagr_positive_trend(self):
        eq = _equity_curve(252 * 2, drift=0.001)
        m = compute_metrics(eq, pd.DataFrame())
        assert m["cagr"] > 0

    def test_max_drawdown_duration(self):
        """In der Drawdown-Equity sind 50 Bars im Drawdown."""
        eq = _drawdown_equity()
        m = compute_metrics(eq, pd.DataFrame())
        assert m["max_drawdown_duration_days"] >= 50


# ---------------------------------------------------------------------------
# compute_slippage
# ---------------------------------------------------------------------------

class TestComputeSlippage:
    def test_base_slippage_no_volume_impact(self):
        """Kleinste Order vs. großes Volumen → nur Base-Spread."""
        slip = compute_slippage(100.0, order_size=1, avg_daily_volume=1_000_000,
                                base_pct=0.05, volume_factor=0.1)
        expected = 100.0 * 0.05 / 100
        assert abs(slip - expected) < 0.001

    def test_volume_impact_scales(self):
        """Doppelte Order-Größe → mehr Slippage."""
        slip1 = compute_slippage(100.0, 100, 1_000_000)
        slip2 = compute_slippage(100.0, 200, 1_000_000)
        assert slip2 > slip1

    def test_large_order_high_slippage(self):
        """Order = 50% des Tagesvolumens → Slippage > reiner Base-Spread."""
        base_only = compute_slippage(100.0, 1, 1_000_000,
                                     base_pct=0.05, volume_factor=0.1)
        slip = compute_slippage(100.0, 500_000, 1_000_000,
                                base_pct=0.05, volume_factor=0.1)
        assert slip > base_only

    def test_zero_volume_uses_default(self):
        """avg_daily_volume=0 → Fallback auf Default, kein ZeroDivisionError."""
        slip = compute_slippage(100.0, 100, 0)
        assert slip > 0

    def test_returns_positive(self):
        slip = compute_slippage(50.0, 10, 500_000)
        assert slip > 0


# ---------------------------------------------------------------------------
# walk_forward_backtest
# ---------------------------------------------------------------------------

class TestWalkForwardBacktest:
    def _buy_hold_strategy(self, train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
        """Immer Long (1)."""
        return pd.Series(1, index=test_df.index)

    def _flat_strategy(self, train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
        """Immer Flat (0)."""
        return pd.Series(0, index=test_df.index)

    def test_basic_run_returns_dict(self):
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        assert isinstance(result, dict)
        assert "fold_results" in result
        assert "equity_curve" in result
        assert result["n_folds"] > 0

    def test_n_folds_count(self):
        """400 Zeilen, 150 train, 50 test, step 50 → (400-150)//50 = 5 Folds."""
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        assert result["n_folds"] == 5

    def test_flat_strategy_zero_return(self):
        """Flat-Strategie → kein Trade → Return nahe 0."""
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._flat_strategy,
                                       train_window=150, test_window=50, step=50)
        assert abs(result["total_return"]) < 0.01

    def test_equity_curve_length(self):
        """Equity-Kurve muss alle Test-Bars abdecken."""
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        # 5 Folds × 50 Bars = 250 Bars in der Equity-Kurve
        assert len(result["equity_curve"]) == 250

    def test_insufficient_data_raises(self):
        df = _make_ohlcv(100)
        with pytest.raises(ValueError, match="mind."):
            walk_forward_backtest(df, self._buy_hold_strategy,
                                  train_window=80, test_window=80, step=20)

    def test_fold_results_structure(self):
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        for fold in result["fold_results"]:
            assert "start" in fold
            assert "end" in fold
            assert "total_return" in fold
            assert "sharpe" in fold
            assert "n_trades" in fold

    def test_strategy_exception_handled(self):
        def bad_strategy(train_df, test_df):
            raise RuntimeError("Strategie kaputt")

        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, bad_strategy,
                                       train_window=150, test_window=50, step=50)
        for fold in result["fold_results"]:
            assert "error" in fold

    def test_n_folds_profitable(self):
        """Buy-and-Hold in ansteigendem Markt → mehrere profitable Folds."""
        rng = np.random.default_rng(99)
        n = 500
        close = 100.0 + np.cumsum(rng.normal(0.2, 0.5, n))
        close = np.clip(close, 1.0, None)
        df = pd.DataFrame(
            {"Open": close, "High": close * 1.005, "Low": close * 0.995,
             "Close": close, "Volume": 1e6},
            index=pd.date_range("2021-01-04", periods=n, freq="B"),
        )
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        assert result["n_folds_profitable"] > 0

    def test_mean_sharpe_is_float(self):
        df = _make_ohlcv(400)
        result = walk_forward_backtest(df, self._buy_hold_strategy,
                                       train_window=150, test_window=50, step=50)
        assert isinstance(result["mean_sharpe"], float)
