"""
StockMind – Tests für RiskManager

Alle Tests laufen offline mit synthetischen Daten.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))

from modules.risk_manager import RiskManager, _ticker_market  # noqa: E402


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 30, base: float = 100.0) -> pd.DataFrame:
    """Synthetischer OHLCV-DataFrame mit n Zeilen."""
    rng   = np.random.default_rng(0)
    close = base + np.cumsum(rng.normal(0, 1, n))
    close = np.clip(close, 1.0, None)
    high  = close * (1 + rng.uniform(0, 0.015, n))
    low   = close * (1 - rng.uniform(0, 0.015, n))
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": 1e6},
        index=pd.date_range("2024-01-01", periods=n, freq="B"),
    )


# ---------------------------------------------------------------------------
# position_size
# ---------------------------------------------------------------------------

class TestPositionSize:
    def test_basic_20_shares(self):
        """
        10k€ Equity, 100€ Einstieg, 95€ SL, 2% Risk, 20% max Position.
        risk_eur = 200, risk/share = 5, uncapped = 40
        cap = 10000 * 20% / 100€ = 20 → result = min(40, 20) = 20
        """
        rm = RiskManager(max_risk_per_trade_pct=2.0, max_position_size_pct=20.0)
        assert rm.position_size(10_000, 100.0, 95.0) == 20

    def test_risk_cap_applies(self):
        """Risk-basierte Größe überschreitet Position-Cap → Cap greift."""
        rm = RiskManager(max_risk_per_trade_pct=5.0, max_position_size_pct=10.0)
        # risk: 500 / 5 = 100 shares
        # cap:  10000 * 10% / 100 = 10 shares
        assert rm.position_size(10_000, 100.0, 95.0) == 10

    def test_position_cap_applies(self):
        """Kleines SL-Abstand → viele Shares, aber Position-Cap greift."""
        rm = RiskManager(max_risk_per_trade_pct=2.0, max_position_size_pct=25.0)
        # risk: 200 / 5 = 40; cap: 10000*25%/100 = 25
        assert rm.position_size(10_000, 100.0, 95.0) == 25

    def test_zero_equity(self):
        rm = RiskManager()
        assert rm.position_size(0, 100.0, 95.0) == 0

    def test_zero_entry_price(self):
        rm = RiskManager()
        assert rm.position_size(10_000, 0.0, 95.0) == 0

    def test_equal_entry_and_sl(self):
        """SL = Entry → kein Risk-Abstand → 0 Stück."""
        rm = RiskManager()
        assert rm.position_size(10_000, 100.0, 100.0) == 0

    def test_negative_equity(self):
        rm = RiskManager()
        assert rm.position_size(-100, 100.0, 95.0) == 0

    def test_small_equity(self):
        """500€ Equity, 100€ Aktie, 95€ SL, 2% Risk, 25% cap."""
        rm = RiskManager(max_risk_per_trade_pct=2.0, max_position_size_pct=25.0)
        # risk: 10/5 = 2; cap: 500*25%/100 = 1.25 → int = 1
        assert rm.position_size(500, 100.0, 95.0) == 1


# ---------------------------------------------------------------------------
# compute_stops (ATR-basiert)
# ---------------------------------------------------------------------------

class TestComputeStops:
    def test_long_sl_below_entry(self):
        df = _make_ohlcv(30)
        rm = RiskManager()
        sl, tp = rm.compute_stops(df, entry_price=100.0, side="LONG")
        assert sl < 100.0
        assert tp > 100.0

    def test_short_sl_above_entry(self):
        df = _make_ohlcv(30)
        rm = RiskManager()
        sl, tp = rm.compute_stops(df, entry_price=100.0, side="SHORT")
        assert sl > 100.0
        assert tp < 100.0

    def test_risk_reward_ratio(self):
        """Take-Profit sollte weiter entfernt sein als Stop-Loss (Standardconfig 2:3)."""
        df = _make_ohlcv(30)
        rm = RiskManager(stop_loss_atr_multiple=2.0, take_profit_atr_multiple=3.0)
        sl, tp = rm.compute_stops(df, entry_price=100.0, side="LONG")
        sl_dist = abs(100.0 - sl)
        tp_dist = abs(tp - 100.0)
        assert tp_dist > sl_dist

    def test_fallback_on_single_row(self):
        """Wenige Daten → Fallback auf 2% ATR."""
        df = _make_ohlcv(1)
        rm = RiskManager()
        sl, tp = rm.compute_stops(df, entry_price=100.0)
        assert sl < 100.0
        assert tp > 100.0

    def test_atr_multiple_scaling(self):
        """Doppeltes ATR-Vielfaches → doppelter SL-Abstand."""
        df = _make_ohlcv(30)
        rm1 = RiskManager(stop_loss_atr_multiple=1.0, take_profit_atr_multiple=1.5)
        rm2 = RiskManager(stop_loss_atr_multiple=2.0, take_profit_atr_multiple=3.0)
        sl1, _ = rm1.compute_stops(df, 100.0)
        sl2, _ = rm2.compute_stops(df, 100.0)
        # rm2 hat doppeltes Multiple → SL weiter weg
        assert (100.0 - sl2) > (100.0 - sl1) * 1.5


# ---------------------------------------------------------------------------
# check_drawdown
# ---------------------------------------------------------------------------

class TestCheckDrawdown:
    def test_no_drawdown(self):
        rm = RiskManager(max_drawdown_pct=15.0)
        curve = [10_000, 10_100, 10_200, 10_300]
        assert rm.check_drawdown(curve) is False

    def test_drawdown_trigger(self):
        """16% Drawdown bei 15% Schwelle → True (pausieren)."""
        rm = RiskManager(max_drawdown_pct=15.0)
        # Peak = 10000, jetzt 8400 → DD = -16%
        curve = [10_000, 9_500, 8_400]
        assert rm.check_drawdown(curve) is True

    def test_drawdown_exactly_at_threshold(self):
        """Exakt -15% Drawdown → True."""
        rm = RiskManager(max_drawdown_pct=15.0)
        curve = [10_000, 8_500]
        assert rm.check_drawdown(curve) is True

    def test_drawdown_just_below_threshold(self):
        """14% Drawdown bei 15% Schwelle → False."""
        rm = RiskManager(max_drawdown_pct=15.0)
        curve = [10_000, 8_600]   # -14% → noch ok
        assert rm.check_drawdown(curve) is False

    def test_single_point_curve(self):
        rm = RiskManager()
        assert rm.check_drawdown([10_000]) is False

    def test_empty_curve(self):
        rm = RiskManager()
        assert rm.check_drawdown([]) is False

    def test_current_drawdown_pct_value(self):
        rm = RiskManager()
        curve = [10_000, 9_000]
        dd = rm.current_drawdown_pct(curve)
        assert abs(dd - (-10.0)) < 0.01

    def test_recovery_after_drawdown(self):
        """Erholt sich über altes Peak → kein Drawdown mehr."""
        rm = RiskManager(max_drawdown_pct=15.0)
        curve = [10_000, 8_000, 11_000]   # -20% dann Recovery über 10k
        assert rm.check_drawdown(curve) is False


# ---------------------------------------------------------------------------
# check_exposure
# ---------------------------------------------------------------------------

class TestCheckExposure:
    def _make_positions(self, symbols: list[str], value_per: float = 2_000) -> dict:
        """Erstellt Positionen mit avg_price=100, quantity=value_per/100."""
        return {
            s: {"quantity": value_per / 100, "avg_price": 100.0}
            for s in symbols
        }

    def test_empty_positions_always_ok(self):
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        assert rm.check_exposure({}, "AAPL", 10_000) is True

    def test_within_exposure_limit(self):
        """20% DE-Exposure bei 40% Limit → ok."""
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        pos = self._make_positions(["BMW.DE", "SAP.DE"], 1_000)  # 2×1k = 2k = 20%
        assert rm.check_exposure(pos, "SIE.DE", 10_000) is True

    def test_exposure_limit_exceeded(self):
        """45% DE-Exposure bei 40% Limit → abgelehnt."""
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        pos = self._make_positions(["BMW.DE", "SAP.DE", "ALV.DE"], 1_500)  # 4.5k = 45%
        assert rm.check_exposure(pos, "SIE.DE", 10_000) is False

    def test_different_market_groups_dont_interfere(self):
        """Volle DE-Positionen blocken keine US-Käufe."""
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        pos = self._make_positions(["BMW.DE", "SAP.DE", "ALV.DE"], 2_000)  # 60% DE
        # US-Kauf sollte trotzdem erlaubt sein
        assert rm.check_exposure(pos, "AAPL", 10_000) is True

    def test_crypto_market_group(self):
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        pos = self._make_positions(["BTC-USD", "ETH-USD"], 2_500)  # 50% Crypto
        assert rm.check_exposure(pos, "BTC-USD", 10_000) is False

    def test_zero_equity_returns_true(self):
        rm = RiskManager()
        pos = self._make_positions(["AAPL"])
        assert rm.check_exposure(pos, "MSFT", 0) is True


# ---------------------------------------------------------------------------
# validate_trade
# ---------------------------------------------------------------------------

class TestValidateTrade:
    def _base_args(self) -> dict:
        return dict(
            direction="BUY",
            ticker="AAPL",
            entry_price=100.0,
            equity=10_000.0,
            cash=5_000.0,
            positions={},
            equity_curve=[10_000.0, 10_050.0],
        )

    def test_sell_always_allowed(self):
        rm = RiskManager()
        ok, _ = rm.validate_trade(
            direction="SELL", ticker="AAPL", entry_price=100.0,
            equity=10_000, cash=0, positions={}, equity_curve=[],
        )
        assert ok is True

    def test_valid_buy(self):
        rm = RiskManager()
        ok, reason = rm.validate_trade(**self._base_args())
        assert ok is True
        assert reason == ""

    def test_blocked_by_drawdown(self):
        rm = RiskManager(max_drawdown_pct=15.0)
        args = self._base_args()
        args["equity_curve"] = [10_000, 8_000]   # -20% DD
        ok, reason = rm.validate_trade(**args)
        assert ok is False
        assert "Drawdown" in reason

    def test_blocked_by_exposure(self):
        rm = RiskManager(max_correlated_exposure_pct=40.0)
        args = self._base_args()
        # 45% DE-Exposure
        args["positions"] = {
            "BMW.DE": {"quantity": 15, "avg_price": 100.0},
            "SAP.DE": {"quantity": 15, "avg_price": 100.0},
            "ALV.DE": {"quantity": 15, "avg_price": 100.0},
        }
        args["ticker"] = "SIE.DE"
        ok, reason = rm.validate_trade(**args)
        assert ok is False
        assert "Exposure" in reason

    def test_blocked_by_no_cash(self):
        rm = RiskManager()
        args = self._base_args()
        args["cash"] = 0.0
        ok, reason = rm.validate_trade(**args)
        assert ok is False
        assert "Cash" in reason

    def test_blocked_by_zero_position_size(self):
        """Zu kleines Equity für Risk-Limit → abgelehnt."""
        rm = RiskManager(max_risk_per_trade_pct=0.001, max_position_size_pct=0.001)
        args = self._base_args()
        args["equity"] = 1.0
        ok, reason = rm.validate_trade(**args, stop_loss_price=99.0)
        assert ok is False

    def test_stop_loss_none_skips_size_check(self):
        """Kein SL angegeben → Größen-Check übersprungen."""
        rm = RiskManager()
        args = self._base_args()
        ok, _ = rm.validate_trade(**args, stop_loss_price=None)
        assert ok is True


# ---------------------------------------------------------------------------
# _ticker_market Heuristik
# ---------------------------------------------------------------------------

class TestTickerMarket:
    def test_xetra(self):
        assert _ticker_market("BMW.DE")  == "DE"
        assert _ticker_market("SAP.DE")  == "DE"

    def test_regional_german(self):
        assert _ticker_market("BMW3.F")  == "DE"
        assert _ticker_market("SAP.MU")  == "DE"

    def test_crypto_dash_usd(self):
        assert _ticker_market("BTC-USD") == "CRYPTO"
        assert _ticker_market("ETH-USD") == "CRYPTO"

    def test_us_stock(self):
        assert _ticker_market("AAPL")    == "US"
        assert _ticker_market("MSFT")    == "US"
        assert _ticker_market("TSLA")    == "US"

    def test_case_insensitive(self):
        assert _ticker_market("bmw.de")  == "DE"
        assert _ticker_market("btc-usd") == "CRYPTO"
