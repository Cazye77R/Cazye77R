"""Tests für Strategien, Simulation und die Walk-Forward-Auswahl."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "stockmind"))

from modules.strategies import STRATEGIES, simulate  # noqa: E402
from modules.strategy_selector import select_strategy  # noqa: E402


def _ohlc(close: np.ndarray) -> pd.DataFrame:
    idx = pd.bdate_range("2018-01-01", periods=len(close))
    c = pd.Series(close, index=idx)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.005, "Low": c * 0.995, "Close": c, "Volume": 1e6}, index=idx
    )


def _random_walk(n=1200, drift=0.0, vol=0.01, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _ohlc(100 * np.exp(np.cumsum(rng.normal(drift, vol, n))))


@pytest.mark.parametrize("key", list(STRATEGIES))
def test_every_strategy_returns_binary_aligned_positions(key):
    df = _random_walk(600)
    strat = STRATEGIES[key]
    for params in strat.param_sets()[:3]:
        pos = strat.positions(df, params)
        assert pos.index.equals(df.index)
        assert set(pos.unique()) <= {0.0, 1.0}
        assert not pos.isna().any()


@pytest.mark.parametrize("key", [k for k in STRATEGIES if k != "buy_hold"])
def test_strategies_are_causal(key):
    """Position bei t darf sich nicht ändern, wenn Daten NACH t verändert werden."""
    df = _random_walk(700, seed=3)
    strat = STRATEGIES[key]
    params = strat.param_sets()[0]
    full = strat.positions(df, params)
    cut = 500
    tampered = df.copy()
    tampered.iloc[cut:, tampered.columns.get_loc("Close")] *= 1.5
    tampered["High"] = tampered["Close"] * 1.005
    tampered["Low"] = tampered["Close"] * 0.995
    alt = strat.positions(tampered, params)
    pd.testing.assert_series_equal(full.iloc[:cut], alt.iloc[:cut])


def test_simulate_executes_next_bar_and_charges_costs():
    close = pd.Series([100.0, 110.0, 121.0, 121.0], index=pd.bdate_range("2020-01-01", periods=4))
    pos = pd.Series([1.0, 1.0, 0.0, 0.0], index=close.index)
    r = simulate(close, pos, cost_bps=0)
    # Position von Bar 0 wirkt erst auf die Rendite von Bar 1
    assert r.iloc[0] == 0
    assert r.iloc[1] == pytest.approx(0.10)
    assert r.iloc[2] == pytest.approx(0.10)
    assert r.iloc[3] == 0
    costly = simulate(close, pos, cost_bps=100)
    assert costly.iloc[1] == pytest.approx(0.10 - 0.01)  # Einstieg
    assert costly.iloc[3] == pytest.approx(-0.01)  # Ausstieg


def test_select_strategy_requires_enough_data():
    with pytest.raises(ValueError, match="Zu wenig Daten"):
        select_strategy(_random_walk(300))


def test_select_strategy_finds_trend_in_trending_market():
    # Zwei lange Trendphasen (hoch, runter): Trendfolger sollen beim Crash helfen
    rng = np.random.default_rng(5)
    up = rng.normal(0.002, 0.008, 700)
    down = rng.normal(-0.003, 0.008, 400)
    up2 = rng.normal(0.002, 0.008, 500)
    df = _ohlc(100 * np.exp(np.cumsum(np.concatenate([up, down, up2]))))
    res = select_strategy(df, train_window=252, test_window=63)
    assert res.metrics["n_folds"] >= 10
    assert len(res.oos_returns) == len(res.bh_returns)
    assert res.current["position_now"] in {"INVESTIERT", "CASH"}
    assert res.verdict in {"besser", "schlechter", "unklar", "zu_wenig_daten"}
    # Drawdown der Auswahl soll im Crash nicht schlimmer sein als bei Buy & Hold
    assert (
        res.metrics["auto"]["max_drawdown_pct"] >= res.metrics["buy_hold"]["max_drawdown_pct"] - 5
    )


def test_select_strategy_does_not_see_the_future():
    """Ändern der Daten NACH dem letzten Fold darf frühere Fold-Entscheidungen nicht verändern."""
    df = _random_walk(1000, seed=11)
    a = select_strategy(df, train_window=252, test_window=63)
    tampered = df.copy()
    tampered.iloc[-60:, tampered.columns.get_loc("Close")] *= 2
    tampered["High"], tampered["Low"] = tampered["Close"] * 1.005, tampered["Close"] * 0.995
    b = select_strategy(tampered, train_window=252, test_window=63)
    common = min(len(a.folds), len(b.folds)) - 2
    assert [f.choice for f in a.folds[:common]] == [f.choice for f in b.folds[:common]]


def test_random_walk_rarely_shows_significant_edge():
    """Auf reinem Rauschen darf die Auswahl nicht systematisch 'besser' melden."""
    better = 0
    for seed in range(6):
        res = select_strategy(_random_walk(1100, seed=100 + seed), train_window=252, test_window=63)
        better += res.verdict == "besser"
    assert better <= 1


def test_lab_ui_renders_end_to_end(monkeypatch):
    from streamlit.testing.v1 import AppTest

    df = _random_walk(1500, seed=2)

    def app():
        from unittest import mock

        import streamlit as st
        import ui.tab_lab as lab

        with mock.patch.object(lab, "cached_ohlcv", return_value=st.session_state["df_test"]):
            lab.render("TEST")

    at = AppTest.from_function(app, default_timeout=120)
    at.session_state["df_test"] = df
    at.run()
    at.button(key="btn_lab").click().run()
    assert not at.exception
    assert any("Aktuelle Auswahl" in m.value for m in at.markdown)


def test_strategy_trade_buys_then_is_idempotent_then_sells(tmp_path, monkeypatch):
    from modules import data_fetcher
    from modules.backtester import PaperTrader

    up = _ohlc(100 * np.exp(np.cumsum(np.full(400, 0.003))))
    down = _ohlc(200 * np.exp(np.cumsum(np.full(400, -0.004))))
    frames = {"df": up}
    monkeypatch.setattr(data_fetcher, "fetch_ohlcv", lambda *a, **k: frames["df"])

    pt = PaperTrader(name="strat_test", base_dir=str(tmp_path))
    pt.reset(10_000)
    e1 = pt.strategy_trade("TEST", "trend_filter", {"window": 50})
    assert e1["decision"] == "BUY"
    e2 = pt.strategy_trade("TEST", "trend_filter", {"window": 50})
    assert e2["decision"] == "HOLD_ALREADY_IN"
    frames["df"] = down
    e3 = pt.strategy_trade("TEST", "trend_filter", {"window": 50})
    assert e3["decision"] in {"SELL", "STOP_LOSS"}
    assert "TEST" not in pt.load().positions
    assert pt.strategy_trade("TEST", "gibtsnicht", {})["decision"] == "SKIP"
