"""Tests für den Autopilot (ohne Netzwerk)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "stockmind"))

from modules import autopilot  # noqa: E402


class FakeTrader:
    def __init__(self):
        self.calls = []

    def strategy_trade(self, ticker, key, params, invest_pct=0.2, label=""):
        self.calls.append((ticker, key, params))
        return {"decision": "BUY"}


def _fake_select(verdict):
    def select(df):
        return SimpleNamespace(
            current={"key": "trend_filter", "params": {"window": 50}, "strategy": "Trend"},
            verdict=verdict,
            metrics={"excess_tstat": 2.5},
        )

    return select


@pytest.fixture
def patched(monkeypatch):
    df = pd.DataFrame({"Close": [1.0, 2.0]})
    monkeypatch.setattr(autopilot, "fetch_ohlcv", lambda *a, **k: df)
    selected = {"n": 0}

    def counting(verdict):
        def sel(d):
            selected["n"] += 1
            return _fake_select(verdict)(d)

        return sel

    monkeypatch.setattr(autopilot, "select_strategy", counting("besser"))
    return selected, counting, monkeypatch


def test_run_once_selects_then_trades_and_caches_selection(tmp_path, patched):
    selected, _, _ = patched
    sf, tr = tmp_path / "s.json", FakeTrader()
    autopilot.run_once(["AAA"], tr, state_file=sf, log=lambda m: None)
    autopilot.run_once(["AAA"], tr, state_file=sf, log=lambda m: None)
    assert selected["n"] == 1  # zweiter Lauf nutzt die gespeicherte Auswahl
    assert len(tr.calls) == 2
    assert autopilot.load_state(sf)["AAA"]["key"] == "trend_filter"


def test_reselects_after_reselect_days(tmp_path, patched):
    selected, _, _ = patched
    sf, tr = tmp_path / "s.json", FakeTrader()
    t0 = datetime(2026, 1, 1)
    autopilot.run_once(["AAA"], tr, state_file=sf, now=t0, log=lambda m: None)
    autopilot.run_once(["AAA"], tr, state_file=sf, now=t0 + timedelta(days=3), log=lambda m: None)
    assert selected["n"] == 1
    autopilot.run_once(["AAA"], tr, state_file=sf, now=t0 + timedelta(days=8), log=lambda m: None)
    assert selected["n"] == 2


@pytest.mark.parametrize("verdict", ["schlechter", "zu_wenig_daten"])
def test_does_not_trade_on_bad_verdict_unless_forced(tmp_path, patched, verdict):
    _, counting, mp = patched
    mp.setattr(autopilot, "select_strategy", counting(verdict))
    tr = FakeTrader()
    out = autopilot.run_once(["AAA"], tr, state_file=tmp_path / "s.json", log=lambda m: None)
    assert out[0]["decision"] == "SKIP" and tr.calls == []
    out = autopilot.run_once(
        ["AAA"], tr, state_file=tmp_path / "s.json", force_trade=True, log=lambda m: None
    )
    assert out[0]["decision"] == "BUY"


def test_one_failing_ticker_does_not_stop_the_others(tmp_path, patched):
    _, _, mp = patched

    def fetch(sym, **k):
        if sym == "BAD":
            raise RuntimeError("kaputt")
        return pd.DataFrame({"Close": [1.0, 2.0]})

    mp.setattr(autopilot, "fetch_ohlcv", fetch)
    tr = FakeTrader()
    out = autopilot.run_once(["BAD", "OK"], tr, state_file=tmp_path / "s.json", log=lambda m: None)
    assert [o["decision"] for o in out] == ["ERROR", "BUY"]


def test_run_forever_respects_max_runs_and_stop_file(tmp_path, patched, monkeypatch):
    monkeypatch.setattr(autopilot, "stop_path", lambda: tmp_path / "STOP")
    monkeypatch.setattr(autopilot, "state_path", lambda: tmp_path / "s.json")
    tr = FakeTrader()
    sleeps = []
    n = autopilot.run_forever(["AAA"], interval_min=1, sleep=sleeps.append, max_runs=3, trader=tr)
    assert n == 3 and len(tr.calls) == 3 and sleeps  # zwischen den Läufen wurde gewartet

    (tmp_path / "STOP").write_text("")
    assert autopilot.run_forever(["AAA"], sleep=sleeps.append, trader=tr) == 0
