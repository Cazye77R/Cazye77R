"""
StockMind – Regelbasierte Handelsstrategien (Long/Flat) mit Parameter-Gitter.

Jede Strategie liefert aus den Kursdaten eine Positions-Series (1 = investiert,
0 = Cash). Die Position bei Bar t nutzt nur Daten bis einschließlich t; die
Ausführung erfolgt erst am Close von Bar t+1 (siehe ``simulate``). Damit gibt
es keinen Look-Ahead.

Die Strategien sind bewusst klassisch und transparent. Welche davon (und mit
welchen Parametern) auf einem Wert taugt, entscheidet ``strategy_selector``
per Walk-Forward – nicht dieses Modul.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder-RSI (exponentiell geglättet)."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    # Kein Verlust im Fenster -> RSI 100 (statt NaN)
    return rsi.where(~((loss == 0) & gain.notna()), 100.0)


def _stateful_position(enter: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """Position bleibt bis zum Exit-Signal bestehen (Eintritt gewinnt nie gegen Austritt)."""
    pos = np.zeros(len(enter), dtype=float)
    state = 0.0
    for i in range(len(enter)):
        if state == 0.0 and enter[i]:
            state = 1.0
        elif state == 1.0 and exit_[i]:
            state = 0.0
        pos[i] = state
    return pos


# ---------------------------------------------------------------------------
# Strategien: df, **params -> Position (0/1)
# ---------------------------------------------------------------------------


def buy_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=df.index)


def sma_cross(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    c = df["Close"]
    f, s = c.rolling(fast).mean(), c.rolling(slow).mean()
    return (f > s).astype(float).where(s.notna(), 0.0)


def trend_filter(df: pd.DataFrame, window: int) -> pd.Series:
    c = df["Close"]
    sma = c.rolling(window).mean()
    return (c > sma).astype(float).where(sma.notna(), 0.0)


def rsi_reversion(df: pd.DataFrame, period: int, low: float, high: float) -> pd.Series:
    rsi = _rsi(df["Close"], period)
    pos = _stateful_position((rsi < low).to_numpy(), (rsi > high).to_numpy())
    return pd.Series(pos, index=df.index)


def macd_cross(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.Series:
    c = df["Close"]
    macd = c.ewm(span=fast, adjust=False).mean() - c.ewm(span=slow, adjust=False).mean()
    sig = macd.ewm(span=signal, adjust=False).mean()
    warm = pd.Series(np.arange(len(c)) >= slow + signal, index=c.index)
    return ((macd > sig) & warm).astype(float)


def bollinger_reversion(df: pd.DataFrame, window: int, k: float) -> pd.Series:
    c = df["Close"]
    mid, sd = c.rolling(window).mean(), c.rolling(window).std()
    lower = mid - k * sd
    pos = _stateful_position((c < lower).to_numpy(), (c > mid).to_numpy())
    return pd.Series(pos, index=df.index)


def donchian_breakout(df: pd.DataFrame, entry: int, exit_: int) -> pd.Series:
    c = df["Close"]
    # Vorherige Hochs/Tiefs (shift(1)): ein Ausbruch muss das bisherige Extrem übertreffen
    hi = (
        df["High"].rolling(entry).max().shift(1)
        if "High" in df
        else c.rolling(entry).max().shift(1)
    )
    lo = df["Low"].rolling(exit_).min().shift(1) if "Low" in df else c.rolling(exit_).min().shift(1)
    pos = _stateful_position((c > hi).to_numpy(), (c < lo).to_numpy())
    return pd.Series(pos, index=df.index)


def momentum(df: pd.DataFrame, lookback: int) -> pd.Series:
    """Zeitreihen-Momentum: investiert, wenn die Rendite der letzten ``lookback`` Tage positiv ist."""
    r = df["Close"].pct_change(lookback)
    return (r > 0).astype(float).where(r.notna(), 0.0)


def trend_low_vol(df: pd.DataFrame, trend: int, vol_window: int, vol_quantile: float) -> pd.Series:
    """Trend-Filter, aber nur bei unterdurchschnittlicher Volatilität (Krisen meiden)."""
    c = df["Close"]
    sma = c.rolling(trend).mean()
    vol = c.pct_change().rolling(vol_window).std()
    # Schwelle nur aus Vergangenheit (expanding), nicht aus der ganzen Reihe
    thresh = vol.expanding(min_periods=vol_window * 2).quantile(vol_quantile)
    ok = (c > sma) & (vol <= thresh)
    return ok.astype(float).where(sma.notna() & thresh.notna(), 0.0)


def dip_in_uptrend(df: pd.DataFrame, trend: int, rsi_period: int, rsi_low: float) -> pd.Series:
    """Rücksetzer im Aufwärtstrend kaufen, verkaufen wenn der Trend bricht oder RSI überhitzt."""
    c = df["Close"]
    sma = c.rolling(trend).mean()
    rsi = _rsi(c, rsi_period)
    enter = ((c > sma) & (rsi < rsi_low)).to_numpy()
    exit_ = ((c < sma) | (rsi > 70)).to_numpy()
    return pd.Series(_stateful_position(enter, exit_), index=df.index)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    fn: Callable[..., pd.Series]
    grid: dict[str, list]
    constraint: Callable[[dict], bool] | None = None

    def param_sets(self) -> list[dict]:
        if not self.grid:
            return [{}]
        names = list(self.grid)
        combos = (dict(zip(names, vals)) for vals in itertools.product(*self.grid.values()))
        return [p for p in combos if self.constraint is None or self.constraint(p)]

    def positions(self, df: pd.DataFrame, params: dict) -> pd.Series:
        pos = self.fn(df, **params)
        return pos.reindex(df.index).fillna(0.0).astype(float)


STRATEGIES: dict[str, Strategy] = {
    s.key: s
    for s in [
        Strategy("buy_hold", "Buy & Hold", buy_hold, {}),
        Strategy(
            "sma_cross",
            "SMA-Kreuzung",
            sma_cross,
            {"fast": [10, 20, 50], "slow": [50, 100, 200]},
            lambda p: p["fast"] < p["slow"],
        ),
        Strategy("trend_filter", "Trend (Kurs > SMA)", trend_filter, {"window": [50, 100, 200]}),
        Strategy(
            "rsi_reversion",
            "RSI Mean-Reversion",
            rsi_reversion,
            {"period": [7, 14], "low": [25, 30, 35], "high": [55, 65, 75]},
        ),
        Strategy(
            "macd_cross",
            "MACD-Kreuzung",
            macd_cross,
            {"fast": [8, 12], "slow": [21, 26], "signal": [9]},
        ),
        Strategy(
            "bollinger_reversion",
            "Bollinger Mean-Reversion",
            bollinger_reversion,
            {"window": [20, 40], "k": [1.5, 2.0, 2.5]},
        ),
        Strategy(
            "donchian_breakout",
            "Donchian-Ausbruch",
            donchian_breakout,
            {"entry": [20, 55], "exit_": [10, 20]},
            lambda p: p["exit_"] < p["entry"],
        ),
        Strategy("momentum", "Zeitreihen-Momentum", momentum, {"lookback": [60, 120, 250]}),
        Strategy(
            "trend_low_vol",
            "Trend + niedrige Volatilität",
            trend_low_vol,
            {"trend": [100, 200], "vol_window": [20], "vol_quantile": [0.6, 0.8]},
        ),
        Strategy(
            "dip_in_uptrend",
            "Rücksetzer im Aufwärtstrend",
            dip_in_uptrend,
            {"trend": [100, 200], "rsi_period": [5, 14], "rsi_low": [30, 40]},
        ),
    ]
}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def simulate(close: pd.Series, position: pd.Series, cost_bps: float = 10.0) -> pd.Series:
    """
    Tägliche Netto-Renditen einer Positions-Series.

    Position von Bar t wirkt erst auf die Rendite von t+1 (Ausführung am
    nächsten Close). Jede Positionsänderung kostet ``cost_bps`` Basispunkte
    (Spread + Slippage + Gebühr in einem Satz, je Richtung).
    """
    ret = close.pct_change().fillna(0.0)
    held = position.shift(1).fillna(0.0)
    turnover = held.diff().abs().fillna(held.abs())
    return held * ret - turnover * cost_bps / 10_000


def annualized_sharpe(returns: pd.Series) -> float:
    if len(returns) < 2:
        return float("nan")
    sd = float(returns.std())
    if sd < 1e-12:
        return float("nan")
    return float(returns.mean() / sd * np.sqrt(TRADING_DAYS))


def max_drawdown_pct(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    eq = (1 + returns).cumprod()
    return float(((eq / eq.cummax()) - 1).min() * 100)


def total_return_pct(returns: pd.Series) -> float:
    return float(((1 + returns).prod() - 1) * 100) if len(returns) else 0.0
