"""
StockMind – Paper-Trading & Backtesting
Simuliert Handelssignale auf historischen Daten und verwaltet ein virtuelles Portfolio.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DEFAULT_BUDGET_EUR, ORDER_COST_EUR, SPREAD_PERCENT, PORTFOLIO_DIR


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    date: str
    ticker: str
    action: str          # "BUY" | "SELL"
    shares: float
    price: float
    cost: float          # inkl. Ordergebühr & Spread
    pnl: float = 0.0    # realisierter G/V (nur bei SELL)
    signal: str = ""


@dataclass
class Portfolio:
    budget: float = DEFAULT_BUDGET_EUR
    cash: float = DEFAULT_BUDGET_EUR
    positions: dict = field(default_factory=dict)   # ticker → {shares, avg_price}
    trades: list[Trade] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Portfolio-Persistenz
# ---------------------------------------------------------------------------

def _portfolio_path(name: str = "default") -> Path:
    p = Path(PORTFOLIO_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.json"


def load_portfolio(name: str = "default") -> Portfolio:
    p = _portfolio_path(name)
    if p.exists():
        with open(p) as f:
            data = json.load(f)
        pf = Portfolio(
            budget=data["budget"],
            cash=data["cash"],
            positions=data.get("positions", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
        pf.trades = [Trade(**t) for t in data.get("trades", [])]
        return pf
    return Portfolio()


def save_portfolio(pf: Portfolio, name: str = "default") -> None:
    data = {
        "budget": pf.budget,
        "cash": pf.cash,
        "positions": pf.positions,
        "created_at": pf.created_at,
        "trades": [asdict(t) for t in pf.trades],
    }
    with open(_portfolio_path(name), "w") as f:
        json.dump(data, f, indent=2, default=str)


def list_portfolios() -> list[str]:
    p = Path(PORTFOLIO_DIR)
    if not p.exists():
        return []
    return [f.stem for f in p.glob("*.json")]


def reset_portfolio(name: str = "default", budget: float = DEFAULT_BUDGET_EUR) -> Portfolio:
    pf = Portfolio(budget=budget, cash=budget)
    save_portfolio(pf, name)
    return pf


# ---------------------------------------------------------------------------
# Handelsoperationen
# ---------------------------------------------------------------------------

def _effective_price(price: float, action: str) -> float:
    """Berechnet Preis nach Spread."""
    spread = price * SPREAD_PERCENT / 100
    return price + spread if action == "BUY" else price - spread


def execute_trade(
    pf: Portfolio,
    ticker: str,
    action: str,
    price: float,
    signal: str = "",
    fraction: float = 0.1,   # Anteil des Cashs der investiert wird (bei BUY)
) -> tuple[bool, str]:
    """
    Führt einen Paper-Trade aus.

    Returns:
        (Erfolg: bool, Nachricht: str)
    """
    eff_price = _effective_price(price, action)
    pnl = 0.0

    if action == "BUY":
        invest = pf.cash * fraction
        total_cost = invest + ORDER_COST_EUR
        if total_cost > pf.cash:
            return False, "Nicht genug Cash für diese Order."
        shares = invest / eff_price
        pf.cash -= total_cost
        pos = pf.positions.get(ticker, {"shares": 0.0, "avg_price": 0.0})
        total_shares = pos["shares"] + shares
        pos["avg_price"] = (pos["shares"] * pos["avg_price"] + shares * eff_price) / total_shares
        pos["shares"] = total_shares
        pf.positions[ticker] = pos

    elif action == "SELL":
        pos = pf.positions.get(ticker)
        if not pos or pos["shares"] <= 0:
            return False, f"Keine Position in {ticker} vorhanden."
        shares = pos["shares"]
        revenue = shares * eff_price - ORDER_COST_EUR
        pnl = revenue - shares * pos["avg_price"]
        pf.cash += revenue
        del pf.positions[ticker]
    else:
        return False, f"Unbekannte Aktion: {action}"

    trade = Trade(
        date=datetime.now().isoformat(),
        ticker=ticker,
        action=action,
        shares=round(shares, 6),
        price=round(price, 4),
        cost=ORDER_COST_EUR,
        pnl=round(pnl, 2),
        signal=signal,
    )
    pf.trades.append(trade)
    return True, f"{action} {shares:.4f} × {ticker} @ {price:.2f} € | PnL: {pnl:+.2f} €"


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    ticker: str
    total_return_pct: float
    buy_and_hold_pct: float
    num_trades: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: list[dict]
    equity_curve: list[float]


def backtest_signals(
    ticker: str,
    df: pd.DataFrame,
    signals: pd.Series,       # pd.Series mit Werten "KAUFEN" | "HALTEN" | "VERKAUFEN"
    initial_cash: float = DEFAULT_BUDGET_EUR,
) -> BacktestResult:
    """
    Simuliert Handelssignale auf einem historischen DataFrame.

    Args:
        ticker:       Aktien-Ticker
        df:           OHLCV-DataFrame
        signals:      Series mit Signal je Datum (gleicher Index wie df)
        initial_cash: Startkapital

    Returns:
        BacktestResult mit Performance-Kennzahlen
    """
    cash = initial_cash
    shares = 0.0
    avg_price = 0.0
    equity_curve = []
    trades = []

    aligned = df[["Close"]].copy()
    aligned["signal"] = signals.reindex(df.index).fillna("HALTEN")

    for date, row in aligned.iterrows():
        price = float(row["Close"])
        sig = row["signal"]
        eff_buy = _effective_price(price, "BUY")
        eff_sell = _effective_price(price, "SELL")

        if sig == "KAUFEN" and cash > ORDER_COST_EUR * 2 and shares == 0:
            invest = cash * 0.95
            new_shares = invest / eff_buy
            cash -= invest + ORDER_COST_EUR
            avg_price = eff_buy
            shares = new_shares
            trades.append({"date": str(date), "action": "BUY", "price": price, "shares": shares})

        elif sig == "VERKAUFEN" and shares > 0:
            revenue = shares * eff_sell - ORDER_COST_EUR
            pnl = revenue - shares * avg_price
            cash += revenue
            trades.append({"date": str(date), "action": "SELL", "price": price, "shares": shares, "pnl": pnl})
            shares = 0.0

        equity = cash + shares * price
        equity_curve.append(equity)

    # Letzte Position schließen
    final_price = float(aligned["Close"].iloc[-1])
    if shares > 0:
        cash += shares * _effective_price(final_price, "SELL") - ORDER_COST_EUR
        shares = 0.0

    final_equity = cash
    total_return_pct = (final_equity - initial_cash) / initial_cash * 100
    buy_and_hold_pct = (
        float(aligned["Close"].iloc[-1]) / float(aligned["Close"].iloc[0]) - 1
    ) * 100

    # Win-Rate
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    wins = [t for t in sell_trades if t.get("pnl", 0) > 0]
    win_rate = len(wins) / len(sell_trades) if sell_trades else 0.0

    # Max Drawdown
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / np.where(peak == 0, 1, peak)
    max_drawdown_pct = float(drawdown.min() * 100)

    # Sharpe Ratio (annualisiert, Risk-Free = 0)
    daily_returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe = (
        float(daily_returns.mean() / daily_returns.std() * np.sqrt(252))
        if daily_returns.std() > 0 else 0.0
    )

    return BacktestResult(
        ticker=ticker,
        total_return_pct=round(total_return_pct, 2),
        buy_and_hold_pct=round(buy_and_hold_pct, 2),
        num_trades=len(trades),
        win_rate=round(win_rate, 3),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        sharpe_ratio=round(sharpe, 3),
        trades=trades,
        equity_curve=equity_curve,
    )


def portfolio_summary(pf: Portfolio, current_prices: dict[str, float]) -> dict:
    """
    Berechnet aktuelle Portfoliokennzahlen.

    Args:
        pf:             Portfolio-Objekt
        current_prices: {ticker: aktueller_kurs}
    """
    position_value = sum(
        pos["shares"] * current_prices.get(ticker, pos["avg_price"])
        for ticker, pos in pf.positions.items()
    )
    total_value = pf.cash + position_value
    total_return = total_value - pf.budget
    total_return_pct = total_return / pf.budget * 100

    positions_detail = []
    for ticker, pos in pf.positions.items():
        curr = current_prices.get(ticker, pos["avg_price"])
        pnl = (curr - pos["avg_price"]) * pos["shares"]
        pnl_pct = (curr / pos["avg_price"] - 1) * 100
        positions_detail.append({
            "ticker": ticker,
            "shares": round(pos["shares"], 4),
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(curr, 2),
            "value": round(pos["shares"] * curr, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    return {
        "cash": round(pf.cash, 2),
        "position_value": round(position_value, 2),
        "total_value": round(total_value, 2),
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "num_trades": len(pf.trades),
        "positions": positions_detail,
    }
