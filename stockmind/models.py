"""
StockMind – Kanonische Pydantic-Datenmodelle.

Diese Modelle dienen als Single Source of Truth für alle zentralen
Datenstrukturen. Module können sie optional zur Validierung nutzen;
bestehende dataclasses bleiben für Abwärtskompatibilität erhalten.

Pydantic v2 (≥ 2.0) wird vorausgesetzt (transitive Abhängigkeit via Streamlit).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Marktdaten
# ---------------------------------------------------------------------------


class OHLCVBar(BaseModel):
    """Einzelne OHLCV-Kerze (ein Handelstag / -intervall)."""

    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def _high_gte_low(self) -> OHLCVBar:
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) muss ≥ low ({self.low}) sein.")
        return self

    @model_validator(mode="after")
    def _high_gte_open_close(self) -> OHLCVBar:
        if self.high < max(self.open, self.close):
            raise ValueError("high muss ≥ max(open, close) sein.")
        return self


class Indicator(BaseModel):
    """Einzelner technischer Indikator mit Signaleinschätzung."""

    name: str
    value: float
    signal: str = ""  # "KAUFEN" | "HALTEN" | "VERKAUFEN" | ""

    @field_validator("signal")
    @classmethod
    def _valid_signal(cls, v: str) -> str:
        allowed = {"KAUFEN", "HALTEN", "VERKAUFEN", ""}
        if v not in allowed:
            raise ValueError(f"signal muss in {allowed} liegen, nicht {v!r}.")
        return v


# ---------------------------------------------------------------------------
# Handelssignal
# ---------------------------------------------------------------------------


class TradeSignal(BaseModel):
    """Ausgabe der Prognose-Pipeline für einen Ticker."""

    ticker: str
    signal: str  # "KAUFEN" | "HALTEN" | "VERKAUFEN"
    confidence: float = Field(ge=0.0, le=1.0)
    method: str = ""
    ml_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    horizon_days: int = Field(default=5, ge=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("signal")
    @classmethod
    def _valid_signal(cls, v: str) -> str:
        allowed = {"KAUFEN", "HALTEN", "VERKAUFEN"}
        if v not in allowed:
            raise ValueError(f"signal muss in {allowed} liegen, nicht {v!r}.")
        return v


# ---------------------------------------------------------------------------
# Portfolio-Strukturen
# ---------------------------------------------------------------------------


class Position(BaseModel):
    """Offene Handelsposition in einem Symbol."""

    symbol: str
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)
    opened_at: datetime
    last_updated: datetime
    market_value: Optional[float] = None  # wird bei Bedarf berechnet

    @property
    def unrealized_pnl(self) -> Optional[float]:
        if self.market_value is None:
            return None
        return self.market_value - self.quantity * self.avg_price


class Portfolio(BaseModel):
    """Vollständiger Portfolio-Zustand (Snapshot)."""

    name: str
    start_budget: float = Field(gt=0)
    cash: float = Field(ge=0)
    positions: dict[str, Position] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_invested(self) -> float:
        return sum(
            p.quantity * p.avg_price for p in self.positions.values()
        )

    @property
    def equity(self) -> float:
        """Cash + Buchwert aller Positionen (ohne aktuelle Marktpreise)."""
        return self.cash + self.total_invested


# ---------------------------------------------------------------------------
# Backtest-Ergebnis
# ---------------------------------------------------------------------------


class BacktestResult(BaseModel):
    """Ergebnis eines Signal-Backtests."""

    ticker: str
    total_return_pct: float
    buy_and_hold_pct: float
    num_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    max_drawdown_pct: float = Field(le=0.0)
    sharpe_ratio: float
    trades: list[dict] = Field(default_factory=list)
    equity_curve: list[float] = Field(default_factory=list)

    @field_validator("max_drawdown_pct")
    @classmethod
    def _drawdown_nonpositive(cls, v: float) -> float:
        if v > 0:
            raise ValueError(f"max_drawdown_pct muss ≤ 0 sein, nicht {v}.")
        return v


# ---------------------------------------------------------------------------
# Risk-Konfiguration
# ---------------------------------------------------------------------------


class RiskConfig(BaseModel):
    """Konfigurations-Modell für den RiskManager."""

    max_risk_per_trade_pct: float = Field(default=2.0, gt=0, le=100)
    max_position_size_pct: float = Field(default=25.0, gt=0, le=100)
    max_drawdown_pct: float = Field(default=15.0, gt=0, le=100)
    max_correlated_exposure_pct: float = Field(default=40.0, gt=0, le=100)
    stop_loss_atr_multiple: float = Field(default=2.0, gt=0)
    take_profit_atr_multiple: float = Field(default=3.0, gt=0)

    @model_validator(mode="after")
    def _tp_gt_sl(self) -> RiskConfig:
        if self.take_profit_atr_multiple <= self.stop_loss_atr_multiple:
            raise ValueError(
                f"take_profit_atr_multiple ({self.take_profit_atr_multiple}) "
                f"muss > stop_loss_atr_multiple ({self.stop_loss_atr_multiple}) sein."
            )
        return self
