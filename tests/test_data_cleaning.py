"""Tests für Datenbereinigung, Offline-Cache und Ticker-Notfallsuche."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "stockmind"))

from modules import data_fetcher as df_mod  # noqa: E402


def _raw():
    idx = pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-04"])
    return pd.DataFrame(
        {
            "Open": [10, 10, 0, 11, 12],
            "High": [9, 11, 12, 12, 13],  # Zeile 0: High < Close
            "Low": [9, 9, 10, 10, 11],
            "Close": [10, 10, 11, 11.5, -1],  # letzte Zeile: negativ
            "Volume": [100, np.nan, -5, 100, 100],
        },
        index=idx,
    )


def test_clean_ohlcv_sorts_dedupes_and_repairs():
    out = df_mod.clean_ohlcv(_raw())
    assert out.index.is_monotonic_increasing
    assert not out.index.duplicated().any()
    assert (out["Close"] > 0).all()
    assert (out["High"] >= out[["Open", "Close"]].max(axis=1)).all()
    assert (out["Low"] <= out[["Open", "Close"]].min(axis=1)).all()
    assert (out["Volume"] >= 0).all()
    assert out.attrs["cleaned"]["rows_dropped"] >= 2


def test_with_retry_recovers_from_transient_error(monkeypatch):
    monkeypatch.setattr(df_mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert df_mod._with_retry(flaky) == "ok"
    assert calls["n"] == 3


def test_fetch_falls_back_to_stale_cache(monkeypatch, tmp_path):
    good = pd.DataFrame(
        {"Open": [1.0, 2], "High": [1.0, 2], "Low": [1.0, 2], "Close": [1.0, 2], "Volume": [1, 1]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    monkeypatch.setattr(df_mod, "_fetch_yf_history", lambda *a, **k: None)
    monkeypatch.setattr(df_mod, "_fetch_yf_download", lambda *a, **k: None)
    monkeypatch.setattr(
        df_mod, "_load_cache", lambda s, p, i, allow_stale=False: good if allow_stale else None
    )
    monkeypatch.setattr(df_mod, "_cache_path", lambda *a: tmp_path / "x.parquet")
    (tmp_path / "x.parquet").write_bytes(b"")
    out = df_mod.fetch_ohlcv("ZZZZ", "1y", "1d")
    assert out.attrs.get("stale") is True
    assert not out.empty
    assert any("Veraltete" in i for i in df_mod.get_data_quality_report(out)["issues"])


def test_search_probes_ticker_when_yahoo_search_is_down(monkeypatch):
    monkeypatch.setattr(df_mod, "_yahoo_search", lambda q: [{"error": "down"}])
    monkeypatch.setattr(df_mod, "_search_crypto_static", lambda q: [])
    seen = []

    def probe(sym, period, interval):
        seen.append(sym)
        return pd.DataFrame({"Close": [1, 2]}) if sym == "SAP.DE" else None

    monkeypatch.setattr(df_mod, "_fetch_yf_history", probe)
    res = df_mod.search_stocks("sap")
    assert res and res[0]["symbol"] == "SAP.DE"
    assert seen == ["SAP", "SAP.DE"]
    assert df_mod.search_stocks("not a ticker!!") == []
