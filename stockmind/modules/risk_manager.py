"""
StockMind – Risk-Management-Layer

RiskManager validiert Trades, berechnet positionsgrößen und überwacht
Drawdown- sowie Exposure-Limits. Wird von PaperTrader vor jedem Kauf konsultiert.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (  # noqa: E402
    MAX_CORRELATED_EXPOSURE_PCT,
    MAX_DRAWDOWN_PCT,
    MAX_POSITION_SIZE_PCT,
    MAX_RISK_PER_TRADE_PCT,
    STOP_LOSS_ATR_MULTIPLE,
    TAKE_PROFIT_ATR_MULTIPLE,
)

from modules.logger import logger  # noqa: E402

# ---------------------------------------------------------------------------
# Hilfsfunktion: Markt-Gruppe für Korrelations-Heuristik
# ---------------------------------------------------------------------------

_DE_SUFFIXES = frozenset({"DE", "F", "MU", "BE", "HM", "DU", "HA"})
_CRYPTO_KEYWORDS = frozenset({
    "BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOT", "DOGE", "MATIC",
    "LTC", "BCH", "XLM", "LINK", "AVAX", "ATOM",
})


def _ticker_market(ticker: str) -> str:
    """
    Einfache Markt-Zuordnung für Korrelations-Heuristik.

    Returns:
        "DE" für XETRA/deutsche Regionalbörsen,
        "CRYPTO" für Kryptowährungen,
        "US" als Fallback (US-Aktien, ETFs ohne Suffix)
    """
    t = ticker.upper()
    if "-USD" in t:
        return "CRYPTO"
    base = t.split(".")[0]
    if base in _CRYPTO_KEYWORDS:
        return "CRYPTO"
    sfx = t.rsplit(".", 1)[-1] if "." in t else ""
    if sfx in _DE_SUFFIXES:
        return "DE"
    return "US"


# ---------------------------------------------------------------------------
# RiskManager
# ---------------------------------------------------------------------------

class RiskManager:
    """
    Kapselung aller Risk-Management-Regeln für den Paper-Trader.

    Alle Parameter können beim Instanziieren überschrieben werden,
    sodass die UI sie live verstellen kann ohne die Config-Defaults zu ändern.
    """

    def __init__(
        self,
        max_risk_per_trade_pct:      float = MAX_RISK_PER_TRADE_PCT,
        max_position_size_pct:       float = MAX_POSITION_SIZE_PCT,
        max_drawdown_pct:            float = MAX_DRAWDOWN_PCT,
        max_correlated_exposure_pct: float = MAX_CORRELATED_EXPOSURE_PCT,
        stop_loss_atr_multiple:      float = STOP_LOSS_ATR_MULTIPLE,
        take_profit_atr_multiple:    float = TAKE_PROFIT_ATR_MULTIPLE,
    ) -> None:
        self.max_risk_per_trade_pct      = max_risk_per_trade_pct
        self.max_position_size_pct       = max_position_size_pct
        self.max_drawdown_pct            = max_drawdown_pct
        self.max_correlated_exposure_pct = max_correlated_exposure_pct
        self.stop_loss_atr_multiple      = stop_loss_atr_multiple
        self.take_profit_atr_multiple    = take_profit_atr_multiple

    # ------------------------------------------------------------------
    # 1. Positionsgröße
    # ------------------------------------------------------------------

    def position_size(
        self,
        equity:          float,
        entry_price:     float,
        stop_loss_price: float,
    ) -> int:
        """
        Berechnet die maximale Stückzahl basierend auf Risk-% vom Equity.

        Formel: shares = (equity × risk_pct%) ÷ |entry − stop_loss|
        Gekappt auf max_position_size_pct × equity ÷ entry_price.

        Args:
            equity:          Aktuelles Gesamtvermögen (Cash + Positionen) in €
            entry_price:     Kaufpreis in €
            stop_loss_price: Stop-Loss-Preis in €

        Returns:
            Stückzahl (int ≥ 0); 0 wenn keine sinnvolle Größe berechenbar.
        """
        if equity <= 0 or entry_price <= 0 or stop_loss_price <= 0:
            return 0
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share < 1e-9:
            return 0

        max_risk_eur = equity * self.max_risk_per_trade_pct / 100.0
        risk_based   = max_risk_eur / risk_per_share

        # Obergrenze: max. % des Eigenkapitals in einer Position
        size_cap = (equity * self.max_position_size_pct / 100.0) / entry_price

        return max(0, int(min(risk_based, size_cap)))

    # ------------------------------------------------------------------
    # 2. Stop-Loss / Take-Profit via ATR(14)
    # ------------------------------------------------------------------

    def compute_stops(
        self,
        df_ohlcv:    pd.DataFrame,
        entry_price: float,
        side:        str = "LONG",
    ) -> tuple[float, float]:
        """
        Berechnet Stop-Loss und Take-Profit als Vielfaches von ATR(14).

        Args:
            df_ohlcv:    OHLCV-DataFrame (mind. 15 Zeilen empfohlen)
            entry_price: Einstiegspreis
            side:        "LONG" (Standard) oder "SHORT"

        Returns:
            (stop_loss, take_profit) als float
        """
        atr = self._atr14(df_ohlcv)
        if side.upper() == "LONG":
            sl = entry_price - self.stop_loss_atr_multiple   * atr
            tp = entry_price + self.take_profit_atr_multiple * atr
        else:
            sl = entry_price + self.stop_loss_atr_multiple   * atr
            tp = entry_price - self.take_profit_atr_multiple * atr
        return round(sl, 4), round(tp, 4)

    def _atr14(self, df: pd.DataFrame) -> float:
        """ATR(14) ohne externe Abhängigkeit."""
        if len(df) < 2:
            # Fallback: 2 % des letzten Schlusskurses
            last = float(df["Close"].iloc[-1]) if not df.empty else 1.0
            return last * 0.02

        highs      = df["High"].values.astype(float)
        lows       = df["Low"].values.astype(float)
        closes     = df["Close"].values.astype(float)
        close_prev = np.concatenate([[closes[0]], closes[:-1]])

        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - close_prev),
                np.abs(lows  - close_prev),
            ),
        )
        window = min(14, len(tr))
        return float(np.mean(tr[-window:]))

    # ------------------------------------------------------------------
    # 3. Drawdown-Check
    # ------------------------------------------------------------------

    def check_drawdown(self, equity_curve: list[float]) -> bool:
        """
        Gibt True zurück wenn der aktuelle Drawdown die Pausenschwelle erreicht.

        Args:
            equity_curve: Zeitreihe der Portfoliowerte (ältester zuerst)

        Returns:
            True → Auto-Trade pausieren; False → normal weiterhandeln
        """
        if len(equity_curve) < 2:
            return False
        dd = self.current_drawdown_pct(equity_curve)
        return bool(dd <= -abs(self.max_drawdown_pct))

    def current_drawdown_pct(self, equity_curve: list[float]) -> float:
        """Aktueller Drawdown in Prozent (≤ 0)."""
        if len(equity_curve) < 2:
            return 0.0
        eq   = np.array(equity_curve, dtype=float)
        peak = float(np.maximum.accumulate(eq)[-1])
        if peak <= 0:
            return 0.0
        return round((eq[-1] - peak) / peak * 100, 2)

    # ------------------------------------------------------------------
    # 4. Exposure-Check
    # ------------------------------------------------------------------

    def check_exposure(
        self,
        positions:  dict,
        new_ticker: str,
        equity:     float,
    ) -> bool:
        """
        Prüft ob die korrelierten Positionen nach einem Kauf das Limit überschreiten.

        Korrelations-Heuristik: gleiche Markt-Gruppe (.DE, Crypto, US).

        Args:
            positions:  Aktuelles Positions-Dict (symbol → {quantity, avg_price, …})
            new_ticker: Ticker des geplanten Kaufs
            equity:     Gesamtportfoliowert für %-Berechnung

        Returns:
            True wenn Trade ok (unter Limit), False wenn Limit überschritten.
        """
        if not positions or equity <= 0:
            return True

        new_market        = _ticker_market(new_ticker)
        correlated_value  = sum(
            pos.get("quantity", 0) * pos.get("avg_price", 0)
            for sym, pos in positions.items()
            if _ticker_market(sym) == new_market
        )
        correlated_pct = correlated_value / equity * 100
        ok = correlated_pct < self.max_correlated_exposure_pct
        if not ok:
            logger.debug(
                f"Exposure-Check fehlgeschlagen: {new_market}-Gruppe "
                f"{correlated_pct:.1f}% >= {self.max_correlated_exposure_pct}%"
            )
        return ok

    # ------------------------------------------------------------------
    # 5. Gesamtvalidierung
    # ------------------------------------------------------------------

    def validate_trade(
        self,
        direction:       str,
        ticker:          str,
        entry_price:     float,
        equity:          float,
        cash:            float,
        positions:       dict,
        equity_curve:    list[float],
        stop_loss_price: float | None = None,
    ) -> tuple[bool, str]:
        """
        Umfassende Trade-Validierung. SELLs werden immer genehmigt.

        Args:
            direction:       "BUY" | "SELL"
            ticker:          Aktien-Symbol
            entry_price:     Geplanter Kaufpreis
            equity:          Gesamtportfoliowert (Cash + Positionen)
            cash:            Verfügbares Cash
            positions:       Offene Positionen
            equity_curve:    Portfoliowert-Zeitreihe
            stop_loss_price: Optionaler geplanter Stop-Loss (für Size-Check)

        Returns:
            (True, "")              → Trade genehmigt
            (False, ablehnungsgrund) → Trade abgelehnt
        """
        if direction.upper() == "SELL":
            return True, ""

        # 1. Drawdown-Schutz
        if self.check_drawdown(equity_curve):
            dd = self.current_drawdown_pct(equity_curve)
            return False, (
                f"Drawdown-Schutz aktiv: aktueller Drawdown {dd:.1f}% "
                f"überschreitet Grenze -{self.max_drawdown_pct:.1f}%."
            )

        # 2. Korrelierte Exposure
        if not self.check_exposure(positions, ticker, equity):
            return False, (
                f"Korreliertes Exposure-Limit erreicht "
                f"({self.max_correlated_exposure_pct:.0f}% max für Markt-Gruppe "
                f"'{_ticker_market(ticker)}')."
            )

        # 3. Positionsgröße prüfen (wenn Stop-Loss bekannt)
        if stop_loss_price is not None and stop_loss_price > 0:
            min_size = self.position_size(equity, entry_price, stop_loss_price)
            if min_size == 0:
                return False, (
                    f"Positionsgröße = 0: Equity {equity:.0f}€ zu gering "
                    f"für Risk-Limit {self.max_risk_per_trade_pct:.1f}% "
                    f"bei SL-Abstand {abs(entry_price - stop_loss_price):.2f}€."
                )

        # 4. Cash-Check
        if cash <= 0:
            return False, "Kein Cash verfügbar."

        return True, ""
