"""
StockMind – Unit-Tests

Netzwerk-abhängige Tests sind mit @pytest.mark.skip markiert.
Alle anderen Tests laufen offline mit synthetischen Daten.
"""

import sys
import os

import numpy as np
import pandas as pd
import pytest

# Projekt-Root (eine Ebene über tests/) und stockmind/ in sys.path
_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))


# ---------------------------------------------------------------------------
# Hilfsfunktion: synthetischer OHLCV-DataFrame
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    """Erstellt einen synthetischen OHLCV-DataFrame mit n Zeilen."""
    rng = np.random.default_rng(42)
    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    close = np.clip(close, 1, None)
    high = close * (1 + rng.uniform(0, 0.02, n))
    low = close * (1 - rng.uniform(0, 0.02, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    volume = rng.integers(100_000, 1_000_000, n).astype(float)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_constants_types(self):
        from config import (
            ORDER_COST_EUR, SPREAD_PERCENT, DEFAULT_BUDGET_EUR,
            LAMBO_PRICE_EUR, CACHE_TTL_HOURS, OLLAMA_BASE_URL,
        )
        assert isinstance(ORDER_COST_EUR, float)
        assert isinstance(SPREAD_PERCENT, float)
        assert isinstance(DEFAULT_BUDGET_EUR, float)
        assert isinstance(LAMBO_PRICE_EUR, float)
        assert isinstance(CACHE_TTL_HOURS, int)
        assert OLLAMA_BASE_URL.startswith("http")

    def test_lambo_price_positive(self):
        from config import LAMBO_PRICE_EUR
        assert LAMBO_PRICE_EUR > 0

    def test_analysis_methods_not_empty(self):
        from config import ANALYSIS_METHODS
        assert len(ANALYSIS_METHODS) > 0
        assert "Auto (KI wählt)" in ANALYSIS_METHODS


# ---------------------------------------------------------------------------
# easter_eggs
# ---------------------------------------------------------------------------

class TestEasterEggs:
    def test_eur_format(self):
        from modules.easter_eggs import get_currency_display
        result = get_currency_display(10_000.0, "EUR €")
        assert "€" in result
        assert "10" in result

    def test_usd_conversion(self):
        from modules.easter_eggs import get_currency_display
        result = get_currency_display(10_000.0, "USD $")
        assert "$" in result

    def test_lambo_goal_reached(self):
        from modules.easter_eggs import get_currency_display, CURRENCIES
        lambo_currency = next(c for c in CURRENCIES if "Lambo" in c)
        result = get_currency_display(536_000.0, lambo_currency)
        assert "ZIEL ERREICHT" in result or "1.0000" in result

    def test_lambo_below_goal(self):
        from modules.easter_eggs import get_currency_display, CURRENCIES
        lambo_currency = next(c for c in CURRENCIES if "Lambo" in c)
        result = get_currency_display(1_000.0, lambo_currency)
        assert "ZIEL ERREICHT" not in result

    def test_check_easter_egg_lambo(self):
        from modules.easter_eggs import check_easter_egg
        result = check_easter_egg({
            "total_value": 600_000,
            "total_return_pct": 10,
            "cycles": 5,
            "accuracy": 0.5,
        })
        assert result is not None
        assert len(result) > 0

    def test_check_easter_egg_none_below_threshold(self):
        from modules.easter_eggs import check_easter_egg
        result = check_easter_egg({
            "total_value": 5_000,
            "total_return_pct": 5,
            "cycles": 3,
            "accuracy": 0.4,
        })
        # Kann None oder einen Random-Egg sein – kein Absturz
        assert result is None or isinstance(result, str)

    def test_confetti_marker_is_string(self):
        from modules.easter_eggs import CONFETTI_MARKER
        assert isinstance(CONFETTI_MARKER, str)
        assert len(CONFETTI_MARKER) > 0

    def test_currencies_list(self):
        from modules.easter_eggs import CURRENCIES, CURRENCY_UNLOCK_CLICKS
        assert len(CURRENCIES) >= 4
        assert isinstance(CURRENCY_UNLOCK_CLICKS, int)
        assert CURRENCY_UNLOCK_CLICKS > 0


# ---------------------------------------------------------------------------
# predictor (offline – kein Trainer-Import)
# ---------------------------------------------------------------------------

class TestPredictor:
    def setup_method(self):
        self.df = _make_ohlcv(200)

    def test_predict_returns_prediction(self):
        from modules.predictor import predict, Prediction
        pred = predict("TEST", self.df, ml_bundle=None, training_state=None)
        assert isinstance(pred, Prediction)

    def test_predict_signal_valid(self):
        from modules.predictor import predict
        pred = predict("TEST", self.df, ml_bundle=None, training_state=None)
        assert pred.signal in ("KAUFEN", "HALTEN", "VERKAUFEN")

    def test_predict_confidence_range(self):
        from modules.predictor import predict
        pred = predict("TEST", self.df, ml_bundle=None, training_state=None)
        assert 0.0 <= pred.confidence <= 1.0

    def test_predict_all_methods(self):
        from modules.predictor import predict, SIGNAL_FUNCTIONS
        for method in SIGNAL_FUNCTIONS:
            pred = predict("TEST", self.df, method=method,
                           ml_bundle=None, training_state=None)
            assert pred.signal in ("KAUFEN", "HALTEN", "VERKAUFEN")

    def test_predict_no_crash_short_df(self):
        from modules.predictor import predict
        short_df = _make_ohlcv(30)
        pred = predict("TEST", short_df, ml_bundle=None, training_state=None)
        assert pred is not None

    def test_build_context_string(self):
        from modules.predictor import predict, build_context_string
        pred = predict("TEST", self.df, ml_bundle=None, training_state=None)
        ctx = build_context_string("TEST", self.df, pred)
        assert "TEST" in ctx
        assert "Kurs" in ctx or "Ticker" in ctx

    def test_signal_functions_keys(self):
        from modules.predictor import SIGNAL_FUNCTIONS
        expected = {"SMA Crossover", "RSI", "MACD", "Bollinger Bands"}
        assert expected.issubset(set(SIGNAL_FUNCTIONS.keys()))


# ---------------------------------------------------------------------------
# backtester / PaperTrader
# ---------------------------------------------------------------------------

class TestPaperTrader:
    def setup_method(self):
        from modules.backtester import PaperTrader
        self.pt = PaperTrader("_pytest_tmp", start_budget=10_000.0)
        self.pt.reset(new_budget=10_000.0)

    def teardown_method(self):
        # Aufräumen: Test-Portfolio-Datei löschen
        import os
        from pathlib import Path
        _root = Path(os.path.dirname(os.path.dirname(__file__))) / "stockmind"
        for f in (_root / "data" / "portfolio").glob("_pytest_tmp*.json"):
            f.unlink(missing_ok=True)

    def test_initial_cash(self):
        state = self.pt.load()
        assert abs(state.cash - 10_000.0) < 0.01

    def test_buy_order_ok(self):
        res = self.pt.place_order("AAPL", "BUY", 10.0, 100.0)
        assert res["ok"] is True
        assert res["direction"] == "BUY"

    def test_sell_without_position_fails(self):
        res = self.pt.place_order("AAPL", "SELL", 10.0, 100.0)
        assert res["ok"] is False
        assert "error" in res

    def test_buy_reduces_cash(self):
        before = self.pt.load().cash
        self.pt.place_order("AAPL", "BUY", 10.0, 100.0)
        after = self.pt.load().cash
        assert after < before

    def test_portfolio_summary_keys(self):
        summary = self.pt.get_portfolio_summary({})
        for key in ("total_value", "cash", "position_value",
                    "realized_pnl", "unrealized_pnl", "win_rate"):
            assert key in summary, f"Key fehlt: {key}"

    def test_lambo_helpers(self):
        from modules.backtester import lambo_value, lambo_display, lambo_progress
        assert isinstance(lambo_value(10_000), float)
        assert isinstance(lambo_display(10_000), str)
        pct, msg = lambo_progress(10_000)
        assert 0.0 <= pct <= 100.0
        assert isinstance(msg, str)

    def test_reset_restores_budget(self):
        self.pt.place_order("AAPL", "BUY", 10.0, 100.0)
        self.pt.reset(new_budget=5_000.0)
        state = self.pt.load()
        assert abs(state.cash - 5_000.0) < 0.01
        assert len(state.positions) == 0


# ---------------------------------------------------------------------------
# data_fetcher – nur offline-Tests; Netzwerk-Test übersprungen
# ---------------------------------------------------------------------------

class TestDataFetcher:
    def test_is_valid_ticker_true(self):
        from modules.data_fetcher import is_valid_ticker
        assert is_valid_ticker("AAPL") is True
        assert is_valid_ticker("SAP.DE") is True

    def test_is_valid_ticker_false(self):
        from modules.data_fetcher import is_valid_ticker
        assert is_valid_ticker("") is False

    def test_is_wkn(self):
        from modules.data_fetcher import is_wkn
        assert is_wkn("716460") is True   # SAP WKN
        assert is_wkn("AAPL") is False    # kein WKN-Format

    def test_empty_df_has_error_attr(self):
        from modules.data_fetcher import _empty_df
        df = _empty_df("Testfehler")
        assert df.empty
        assert df.attrs.get("error") == "Testfehler"

    def test_cache_path_extension(self):
        from modules.data_fetcher import _cache_path
        path = _cache_path("AAPL", "1y", "1d")
        assert str(path).endswith(".parquet"), f"Erwartet .parquet, got: {path}"

    @pytest.mark.skip(reason="requires network proxy – Yahoo Finance nicht erreichbar")
    def test_fetch_ohlcv_network(self):
        from modules.data_fetcher import fetch_ohlcv
        df = fetch_ohlcv("SAP.DE", period="1mo")
        assert not df.empty
        assert "Close" in df.columns
