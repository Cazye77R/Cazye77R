"""
StockMind – Paper-Trading & Backtesting
PaperTrader-Klasse: persistierte Trades, Portfolio-KPIs, Lambo-Konverter,
Auto-Trade-Modus via KI-Vorhersagen.
Modul-Funktionen bleiben erhalten (Compat: app.py).
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    DEFAULT_BUDGET_EUR,
    LAMBO_PRICE_EUR,
    ORDER_COST_EUR,
    PORTFOLIO_DIR,
    SPREAD_PERCENT,
)


# ===========================================================================
# Datenklassen
# ===========================================================================

@dataclass
class TradeRecord:
    """Einzelner Trade-Eintrag (BUY oder SELL)."""
    id:           str        # Eindeutige Trade-ID
    symbol:       str
    direction:    str        # "BUY" | "SELL"
    quantity:     float
    price:        float      # Marktpreis
    exec_price:   float      # Tatsächlicher Preis inkl. Spread
    order_cost:   float      # Ordergebühr
    total_cost:   float      # Gesamtkosten / Erlös
    timestamp:    str
    pnl:          float = 0.0     # Realisierter G/V (nur SELL)
    pnl_pct:      float = 0.0
    signal:       str  = ""       # Auslösendes Signal
    reasoning:    str  = ""       # KI-Begründung (Auto-Modus)
    method:       str  = ""       # Analysemethode


@dataclass
class Position:
    """Offene Position in einem Symbol."""
    symbol:       str
    quantity:     float
    avg_price:    float      # Durchschnittlicher Einstandspreis (inkl. Spread)
    opened_at:    str
    last_updated: str


@dataclass
class PortfolioState:
    """Vollständiger Portfolio-Zustand."""
    name:         str
    start_budget: float
    cash:         float
    order_cost:   float      = ORDER_COST_EUR
    spread_pct:   float      = SPREAD_PERCENT
    positions:    dict       = field(default_factory=dict)   # symbol → Position-dict
    trades:       list       = field(default_factory=list)   # list[TradeRecord-dict]
    equity_ts:    list       = field(default_factory=list)   # [{ts, value}]
    created_at:   str        = field(default_factory=lambda: _now())
    auto_log:     list       = field(default_factory=list)   # Auto-Trade Entscheidungs-Log


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _trade_id() -> str:
    """Kurze eindeutige Trade-ID basierend auf UTC-Timestamp."""
    import time
    return f"T{int(time.time()*1000) % 10**10:010d}"


# ===========================================================================
# PaperTrader – Klasse
# ===========================================================================

class PaperTrader:
    """
    Paper-Trading-Engine mit Persistenz unter data/portfolio/{name}_trades.json.

    Konfigurierbare Parameter:
        start_budget : Startkapital in EUR  (Default: 10 000 €)
        order_cost   : Gebühr je Order      (Default: 5 €)
        spread_pct   : Spread in Prozent    (Default: 0,1 %)

    Alle Werte lassen sich über den Konstruktor überschreiben (UI-Override).
    """

    def __init__(
        self,
        name:         str   = "default",
        start_budget: float = DEFAULT_BUDGET_EUR,
        order_cost:   float = ORDER_COST_EUR,
        spread_pct:   float = SPREAD_PERCENT,
        base_dir:     str | None = None,
    ):
        self.name         = name
        self.start_budget = start_budget
        self.order_cost   = order_cost
        self.spread_pct   = spread_pct

        root = Path(os.path.dirname(os.path.dirname(__file__)))
        self._pf_dir = root / (base_dir or PORTFOLIO_DIR)
        self._pf_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Persistenz
    # ------------------------------------------------------------------

    def _path(self) -> Path:
        return self._pf_dir / f"{self.name}_trades.json"

    def load(self) -> PortfolioState:
        """Lädt den Portfolio-Zustand. Erstellt neuen bei fehlendem Zustand."""
        p = self._path()
        if not p.exists():
            return PortfolioState(
                name=self.name,
                start_budget=self.start_budget,
                cash=self.start_budget,
                order_cost=self.order_cost,
                spread_pct=self.spread_pct,
            )
        with open(p) as f:
            data = json.load(f)
        return PortfolioState(
            name=data.get("name", self.name),
            start_budget=data.get("start_budget", self.start_budget),
            cash=data.get("cash", self.start_budget),
            order_cost=data.get("order_cost", self.order_cost),
            spread_pct=data.get("spread_pct", self.spread_pct),
            positions=data.get("positions", {}),
            trades=data.get("trades", []),
            equity_ts=data.get("equity_ts", []),
            created_at=data.get("created_at", _now()),
            auto_log=data.get("auto_log", []),
        )

    def save(self, state: PortfolioState) -> None:
        with open(self._path(), "w") as f:
            json.dump(asdict(state), f, indent=2, default=str)

    def reset(self, new_budget: float | None = None) -> PortfolioState:
        """Setzt das Portfolio zurück (altes Portfolio wird überschrieben)."""
        budget = new_budget if new_budget is not None else self.start_budget
        state = PortfolioState(
            name=self.name,
            start_budget=budget,
            cash=budget,
            order_cost=self.order_cost,
            spread_pct=self.spread_pct,
        )
        self.save(state)
        return state

    # ------------------------------------------------------------------
    # 3a. place_order
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol:    str,
        direction: str,        # "BUY" | "SELL"
        quantity:  float,
        price:     float,
        timestamp: str | None = None,
        signal:    str = "",
        reasoning: str = "",
        method:    str = "",
    ) -> dict:
        """
        Platziert eine Order und aktualisiert Cash + Positionen.

        Berechnet:
          BUY:  exec_price = price * (1 + spread_pct/100)
          SELL: exec_price = price * (1 - spread_pct/100)
          total_cost = quantity * exec_price + order_cost  (BUY)
          total_cost = quantity * exec_price - order_cost  (SELL, Erlös)

        Returns:
            TradeRecord als dict + "ok": True/False + "error": str
        """
        direction = direction.upper()
        if direction not in ("BUY", "SELL"):
            return {"ok": False, "error": f"Ungültige Richtung: {direction!r}"}
        if quantity <= 0:
            return {"ok": False, "error": f"Ungültige Menge: {quantity}"}
        if price <= 0:
            return {"ok": False, "error": f"Ungültiger Preis: {price}"}

        state = self.load()
        ts    = timestamp or _now()

        spread = price * state.spread_pct / 100
        if direction == "BUY":
            exec_price = price + spread
            gross      = quantity * exec_price
            total_cost = gross + state.order_cost
            if total_cost > state.cash:
                return {
                    "ok":    False,
                    "error": (
                        f"Nicht genug Cash: benötigt {total_cost:.2f} €, "
                        f"verfügbar {state.cash:.2f} €"
                    ),
                }
            state.cash -= total_cost

            # Position aktualisieren (avg-Price-Methode)
            pos = state.positions.get(symbol)
            if pos:
                old_qty   = pos["quantity"]
                old_avg   = pos["avg_price"]
                new_qty   = old_qty + quantity
                new_avg   = (old_qty * old_avg + quantity * exec_price) / new_qty
                state.positions[symbol] = {
                    "symbol":       symbol,
                    "quantity":     round(new_qty, 8),
                    "avg_price":    round(new_avg, 6),
                    "opened_at":    pos["opened_at"],
                    "last_updated": ts,
                }
            else:
                state.positions[symbol] = {
                    "symbol":       symbol,
                    "quantity":     round(quantity, 8),
                    "avg_price":    round(exec_price, 6),
                    "opened_at":    ts,
                    "last_updated": ts,
                }
            pnl     = 0.0
            pnl_pct = 0.0

        else:  # SELL
            pos = state.positions.get(symbol)
            if not pos or pos["quantity"] <= 0:
                return {"ok": False, "error": f"Keine offene Position in {symbol}."}
            sell_qty    = min(quantity, pos["quantity"])
            exec_price  = price - spread
            gross       = sell_qty * exec_price
            total_cost  = gross - state.order_cost    # Erlös nach Gebühr
            cost_basis  = sell_qty * pos["avg_price"]
            pnl         = total_cost - cost_basis
            pnl_pct     = pnl / cost_basis * 100 if cost_basis > 0 else 0.0

            state.cash += total_cost
            remaining   = pos["quantity"] - sell_qty
            if remaining > 1e-8:
                state.positions[symbol] = {**pos, "quantity": round(remaining, 8), "last_updated": ts}
            else:
                del state.positions[symbol]

            quantity = sell_qty

        rec = {
            "id":         _trade_id(),
            "symbol":     symbol,
            "direction":  direction,
            "quantity":   round(quantity, 8),
            "price":      round(price, 4),
            "exec_price": round(exec_price, 4),
            "order_cost": round(state.order_cost, 2),
            "total_cost": round(total_cost, 4),
            "timestamp":  ts,
            "pnl":        round(pnl, 4),
            "pnl_pct":    round(pnl_pct, 4),
            "signal":     signal,
            "reasoning":  reasoning,
            "method":     method,
        }
        state.trades.append(rec)

        # Equity-Zeitreihe aktualisieren
        pos_val = sum(
            p["quantity"] * price if p["symbol"] == symbol else p["quantity"] * p["avg_price"]
            for p in state.positions.values()
        )
        state.equity_ts.append({"ts": ts, "value": round(state.cash + pos_val, 2)})

        self.save(state)
        return {"ok": True, "error": "", **rec}

    # ------------------------------------------------------------------
    # 3b. close_position
    # ------------------------------------------------------------------

    def close_position(
        self,
        symbol:    str,
        price:     float,
        timestamp: str | None = None,
        reasoning: str = "",
    ) -> dict:
        """
        Schließt die gesamte offene Position in `symbol`.

        Returns:
            dict mit P&L-Informationen und Trade-Record
        """
        state = self.load()
        pos   = state.positions.get(symbol)
        if not pos or pos["quantity"] <= 0:
            return {"ok": False, "error": f"Keine offene Position in {symbol}."}

        return self.place_order(
            symbol=symbol,
            direction="SELL",
            quantity=pos["quantity"],
            price=price,
            timestamp=timestamp,
            signal="CLOSE",
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # 3c. get_portfolio_summary
    # ------------------------------------------------------------------

    def get_portfolio_summary(
        self,
        current_prices: dict[str, float] | None = None,
    ) -> dict:
        """
        Gibt vollständige Portfolio-Kennzahlen zurück.

        Args:
            current_prices: {symbol: kurs} – wird für offene Positionen benötigt.
                            Fällt auf avg_price zurück wenn nicht angegeben.

        Returns:
            {
              total_value, cash, position_value,
              realized_pnl, unrealized_pnl,
              total_return_pct, win_rate,
              best_trade, worst_trade,
              num_trades, num_open_positions,
              lambo_value, lambo_pct,
              positions: [...], closed_trades: [...]
            }
        """
        state  = self.load()
        prices = current_prices or {}

        # Positions-Werte
        pos_value   = 0.0
        unrealized  = 0.0
        positions_d = []
        for sym, pos in state.positions.items():
            curr  = prices.get(sym, pos["avg_price"])
            val   = pos["quantity"] * curr
            unrlz = (curr - pos["avg_price"]) * pos["quantity"]
            pos_value  += val
            unrealized += unrlz
            positions_d.append({
                "symbol":        sym,
                "quantity":      round(pos["quantity"], 6),
                "avg_price":     round(pos["avg_price"], 4),
                "current_price": round(curr, 4),
                "value":         round(val, 2),
                "unrealized_pnl":    round(unrlz, 2),
                "unrealized_pnl_pct": round(unrlz / (pos["quantity"] * pos["avg_price"]) * 100, 2)
                                       if pos["avg_price"] > 0 else 0.0,
            })

        total_value    = state.cash + pos_value
        realized_pnl   = sum(t.get("pnl", 0.0) for t in state.trades if t["direction"] == "SELL")
        total_return    = total_value - state.start_budget
        total_return_pct = total_return / state.start_budget * 100 if state.start_budget > 0 else 0.0

        # Win / Loss
        sell_trades = [t for t in state.trades if t["direction"] == "SELL"]
        wins        = [t for t in sell_trades if t.get("pnl", 0) > 0]
        losses      = [t for t in sell_trades if t.get("pnl", 0) <= 0]
        win_rate    = len(wins) / len(sell_trades) if sell_trades else 0.0

        best_trade  = max(sell_trades, key=lambda t: t.get("pnl", 0), default=None)
        worst_trade = min(sell_trades, key=lambda t: t.get("pnl", 0), default=None)

        return {
            "total_value":        round(total_value, 2),
            "cash":               round(state.cash, 2),
            "position_value":     round(pos_value, 2),
            "realized_pnl":       round(realized_pnl, 2),
            "unrealized_pnl":     round(unrealized, 2),
            "total_return":       round(total_return, 2),
            "total_return_pct":   round(total_return_pct, 4),
            "win_rate":           round(win_rate, 4),
            "best_trade":         best_trade,
            "worst_trade":        worst_trade,
            "num_trades":         len(state.trades),
            "num_sell_trades":    len(sell_trades),
            "num_open_positions": len(state.positions),
            "lambo_value":        lambo_value(total_value),
            "lambo_pct":          round(total_value / LAMBO_PRICE_EUR * 100, 4),
            "start_budget":       state.start_budget,
            "positions":          positions_d,
            "closed_trades":      sell_trades,
        }

    # ------------------------------------------------------------------
    # 3d. get_performance_chart
    # ------------------------------------------------------------------

    def get_performance_chart(self) -> pd.DataFrame:
        """
        Gibt die Portfolio-Wert-Zeitreihe als DataFrame zurück.

        Returns:
            DataFrame mit Spalten: timestamp (DatetimeIndex), value,
            return_pct, drawdown_pct
            Geeignet für Plotly-Chart.
        """
        state = self.load()
        if not state.equity_ts:
            # Nur Startpunkt
            return pd.DataFrame([{
                "timestamp":   state.created_at,
                "value":       state.start_budget,
                "return_pct":  0.0,
                "drawdown_pct": 0.0,
            }])

        df = pd.DataFrame(state.equity_ts)
        df["timestamp"]  = pd.to_datetime(df["ts"])
        df["value"]      = df["value"].astype(float)
        df["return_pct"] = (df["value"] / state.start_budget - 1) * 100

        # Drawdown
        peak             = df["value"].cummax()
        df["drawdown_pct"] = (df["value"] - peak) / peak.replace(0, float("nan")) * 100

        return df[["timestamp", "value", "return_pct", "drawdown_pct"]].reset_index(drop=True)

    # ------------------------------------------------------------------
    # 5. auto_trade
    # ------------------------------------------------------------------

    def auto_trade(
        self,
        symbol:     str,
        model_name: str,
        cycles:     int = 5,
        method:     str = "Auto (KI wählt)",
        invest_pct: float = 0.2,   # Anteil des Cashs je BUY-Signal
    ) -> list[dict]:
        """
        Automatischer Trading-Modus:
        - Holt KI-Vorhersage via StockTrainer
        - Kauft bei UP-Signal (invest_pct des verfügbaren Cashs)
        - Schließt offene Position bei DOWN-Signal
        - Ignoriert NEUTRAL
        - Loggt alle Entscheidungen mit Begründung

        Args:
            symbol:     Aktien-Symbol
            model_name: Ollama-Modellname
            cycles:     Anzahl Trainingszyklen / Vorhersagen
            method:     Analysemethode ("Auto (KI wählt)" → StockTrainer.auto_mode)
            invest_pct: Anteil des Cashs der pro BUY investiert wird (0.0–1.0)

        Returns:
            Liste der Auto-Log-Einträge dieser Session
        """
        from modules.data_fetcher import fetch_ohlcv
        from modules.trainer import StockTrainer

        trainer  = StockTrainer()
        log      = []

        for i in range(cycles):
            # Vorhersage holen
            if method == "Auto (KI wählt)":
                result = trainer.auto_mode(symbol, model_name)
            else:
                result = trainer.run_training_cycle(symbol, method, model_name)

            if result.get("error"):
                entry = {
                    "cycle":     i + 1,
                    "symbol":    symbol,
                    "decision":  "SKIP",
                    "reason":    result["error"],
                    "timestamp": _now(),
                }
                log.append(entry)
                continue

            prediction = result.get("prediction")
            confidence = result.get("confidence", 0.0)
            reasoning  = result.get("reasoning", "")
            used_method = result.get("method", method)

            # Aktuellen Kurs laden
            df = fetch_ohlcv(symbol, period="5d")
            if df.empty:
                log.append({"cycle": i+1, "decision": "SKIP", "reason": "Kein Kurs abrufbar"})
                continue
            current_price = float(df["Close"].iloc[-1])

            state = self.load()

            # Trading-Logik
            decision = "HOLD"
            trade_result: dict = {}

            if prediction == "UP" and confidence >= 0.5:
                # Kaufen falls kein offene Position UND genug Cash
                if symbol not in state.positions and state.cash > self.order_cost * 3:
                    invest_eur = state.cash * invest_pct
                    quantity   = invest_eur / (current_price * (1 + state.spread_pct / 100))
                    trade_result = self.place_order(
                        symbol=symbol,
                        direction="BUY",
                        quantity=quantity,
                        price=current_price,
                        signal=f"UP/{confidence:.0%}",
                        reasoning=reasoning,
                        method=used_method,
                    )
                    decision = "BUY" if trade_result.get("ok") else "BUY_FAILED"
                else:
                    decision = "HOLD_ALREADY_IN" if symbol in state.positions else "HOLD_LOW_CASH"

            elif prediction == "DOWN" and confidence >= 0.5:
                # Verkaufen falls Position offen
                if symbol in state.positions:
                    trade_result = self.close_position(
                        symbol=symbol,
                        price=current_price,
                        reasoning=reasoning,
                    )
                    decision = "SELL" if trade_result.get("ok") else "SELL_FAILED"
                else:
                    decision = "HOLD_NO_POSITION"
            else:
                decision = "HOLD_NEUTRAL"

            summary = self.get_portfolio_summary({symbol: current_price})
            entry = {
                "cycle":         i + 1,
                "symbol":        symbol,
                "method":        used_method,
                "prediction":    prediction,
                "confidence":    confidence,
                "current_price": current_price,
                "decision":      decision,
                "reasoning":     reasoning[:300],
                "pnl":           trade_result.get("pnl", 0.0),
                "portfolio_value": summary["total_value"],
                "lambo_value":   summary["lambo_value"],
                "timestamp":     _now(),
            }
            log.append(entry)

            # Im Portfolio-Zustand persistieren
            state2 = self.load()
            state2.auto_log.extend(log[-1:])
            state2.auto_log = state2.auto_log[-50:]   # Maximal 50 Einträge
            self.save(state2)

        return log


# ===========================================================================
# 4. Lambo-Konverter (Modul-Ebene)
# ===========================================================================

def lambo_value(eur_value: float) -> float:
    """
    Rechnet EUR in Lamborghini Aventador SVJ um.

    Beispiel: lambo_value(12_000) → 0.0224 (Lambos)

    Returns:
        Float – Anzahl Lambos (üblicherweise < 1)
    """
    if LAMBO_PRICE_EUR <= 0:
        return 0.0
    return round(eur_value / LAMBO_PRICE_EUR, 8)


def lambo_display(eur_value: float) -> str:
    """Gibt lesbaren Lambo-String zurück, z.B. '0.0224 🏎️ Lambos'."""
    lv = lambo_value(eur_value)
    if lv >= 1.0:
        return f"{lv:.4f} 🏎️ Lambos (ZIEL ERREICHT! 🎉)"
    if lv >= 0.1:
        return f"{lv:.4f} 🏎️ Lambos ({lv*100:.1f}% eines Lambos)"
    if lv >= 0.01:
        return f"{lv:.4f} 🏎️ Lambos ({lv*100:.2f}% eines Lambos)"
    return f"{lv:.6f} 🏎️ Lambos (noch ein langer Weg…)"


def lambo_progress(eur_value: float) -> tuple[float, str]:
    """Gibt (Prozent 0-100, Motivationstext) für den Lambo-Fortschrittsbalken zurück."""
    pct = min(100.0, eur_value / LAMBO_PRICE_EUR * 100)
    if pct >= 100:  msg = "🏎️ LAMBO UNLOCKED! Herzlichen Glückwunsch!"
    elif pct >= 75: msg = "🔥 Noch ein letzter Sprint!"
    elif pct >= 50: msg = "💪 Halbzeit! Du schaffst das!"
    elif pct >= 25: msg = "📈 Solide Basis. Weiter so!"
    elif pct >= 10: msg = "🌱 Guter Start. Geduld zahlt sich aus."
    else:           msg = "🐣 Der erste Schritt ist getan."
    return pct, msg


# ===========================================================================
# Backward-kompatible Modul-Funktionen (app.py)
# ===========================================================================

# Interne Legacy-Datenklassen (erhalten für app.py-Kompatibilität)
@dataclass
class Trade:
    date:   str
    ticker: str
    action: str
    shares: float
    price:  float
    cost:   float
    pnl:    float = 0.0
    signal: str   = ""


@dataclass
class Portfolio:
    budget:     float = DEFAULT_BUDGET_EUR
    cash:       float = DEFAULT_BUDGET_EUR
    positions:  dict  = field(default_factory=dict)
    trades:     list  = field(default_factory=list)
    created_at: str   = field(default_factory=lambda: datetime.now().isoformat())


def _portfolio_path(name: str = "default") -> Path:
    p = Path(PORTFOLIO_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.json"


def load_portfolio(name: str = "default") -> Portfolio:
    """Lädt ein Legacy-Portfolio (app.py-Compat)."""
    p = _portfolio_path(name)
    if p.exists():
        with open(p) as f:
            data = json.load(f)
        pf = Portfolio(
            budget=data.get("budget", DEFAULT_BUDGET_EUR),
            cash=data.get("cash", DEFAULT_BUDGET_EUR),
            positions=data.get("positions", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
        pf.trades = [Trade(**t) for t in data.get("trades", [])]
        return pf
    return Portfolio()


def save_portfolio(pf: Portfolio, name: str = "default") -> None:
    data = {
        "budget":     pf.budget,
        "cash":       pf.cash,
        "positions":  pf.positions,
        "created_at": pf.created_at,
        "trades":     [asdict(t) for t in pf.trades],
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


def _eff_price(price: float, action: str, spread_pct: float = SPREAD_PERCENT) -> float:
    sp = price * spread_pct / 100
    return price + sp if action == "BUY" else price - sp


# Legacy-Alias für neue Funktion
_effective_price = _eff_price


def execute_trade(
    pf:       Portfolio,
    ticker:   str,
    action:   str,
    price:    float,
    signal:   str   = "",
    fraction: float = 0.1,
) -> tuple[bool, str]:
    """Führt einen Legacy-Paper-Trade aus (app.py-Compat)."""
    eff   = _eff_price(price, action)
    pnl   = 0.0
    shares = 0.0

    if action == "BUY":
        invest     = pf.cash * fraction
        total_cost = invest + ORDER_COST_EUR
        if total_cost > pf.cash:
            return False, "Nicht genug Cash für diese Order."
        shares = invest / eff
        pf.cash -= total_cost
        pos = pf.positions.get(ticker, {"shares": 0.0, "avg_price": 0.0})
        total_sh = pos["shares"] + shares
        pos["avg_price"] = (pos["shares"] * pos["avg_price"] + shares * eff) / total_sh
        pos["shares"]    = total_sh
        pf.positions[ticker] = pos

    elif action == "SELL":
        pos = pf.positions.get(ticker)
        if not pos or pos["shares"] <= 0:
            return False, f"Keine Position in {ticker} vorhanden."
        shares  = pos["shares"]
        revenue = shares * eff - ORDER_COST_EUR
        pnl     = revenue - shares * pos["avg_price"]
        pf.cash += revenue
        del pf.positions[ticker]
    else:
        return False, f"Unbekannte Aktion: {action}"

    pf.trades.append(Trade(
        date=datetime.now().isoformat(), ticker=ticker, action=action,
        shares=round(shares, 6), price=round(price, 4),
        cost=ORDER_COST_EUR, pnl=round(pnl, 2), signal=signal,
    ))
    return True, f"{action} {shares:.4f} × {ticker} @ {price:.2f} € | PnL: {pnl:+.2f} €"


def portfolio_summary(pf: Portfolio, current_prices: dict[str, float]) -> dict:
    """Berechnet Legacy-Portfoliokennzahlen (app.py-Compat)."""
    pos_val = sum(
        pos["shares"] * current_prices.get(t, pos["avg_price"])
        for t, pos in pf.positions.items()
    )
    total         = pf.cash + pos_val
    total_ret     = total - pf.budget
    total_ret_pct = total_ret / pf.budget * 100

    positions_d = []
    for t, pos in pf.positions.items():
        curr    = current_prices.get(t, pos["avg_price"])
        p_pnl   = (curr - pos["avg_price"]) * pos["shares"]
        p_pct   = (curr / pos["avg_price"] - 1) * 100
        positions_d.append({
            "ticker": t, "shares": round(pos["shares"], 4),
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(curr, 2),
            "value": round(pos["shares"] * curr, 2),
            "pnl": round(p_pnl, 2), "pnl_pct": round(p_pct, 2),
        })

    return {
        "cash":              round(pf.cash, 2),
        "position_value":    round(pos_val, 2),
        "total_value":       round(total, 2),
        "total_return":      round(total_ret, 2),
        "total_return_pct":  round(total_ret_pct, 2),
        "num_trades":        len(pf.trades),
        "positions":         positions_d,
    }


# ===========================================================================
# Backtesting-Funktion (app.py Backtesting-Seite)
# ===========================================================================

@dataclass
class BacktestResult:
    ticker:           str
    total_return_pct: float
    buy_and_hold_pct: float
    num_trades:       int
    win_rate:         float
    max_drawdown_pct: float
    sharpe_ratio:     float
    trades:           list
    equity_curve:     list


def backtest_signals(
    ticker:       str,
    df:           pd.DataFrame,
    signals:      pd.Series,
    initial_cash: float = DEFAULT_BUDGET_EUR,
    order_cost:   float = ORDER_COST_EUR,
    spread_pct:   float = SPREAD_PERCENT,
) -> BacktestResult:
    """
    Simuliert Handelssignale auf historischen Daten.

    Args:
        ticker:       Aktien-Symbol
        df:           OHLCV-DataFrame
        signals:      pd.Series mit "KAUFEN" | "HALTEN" | "VERKAUFEN" je Datum
        initial_cash: Startkapital (EUR)
        order_cost:   Ordergebühr (EUR)
        spread_pct:   Spread (%)

    Returns:
        BacktestResult mit Equity-Kurve und Kennzahlen
    """
    cash      = initial_cash
    shares    = 0.0
    avg_price = 0.0
    equity_curve: list[float] = []
    trades:       list[dict]  = []

    aligned           = df[["Close"]].copy()
    aligned["signal"] = signals.reindex(df.index).fillna("HALTEN")

    for date, row in aligned.iterrows():
        price    = float(row["Close"])
        sig      = row["signal"]
        eff_buy  = _eff_price(price, "BUY",  spread_pct)
        eff_sell = _eff_price(price, "SELL", spread_pct)

        if sig == "KAUFEN" and cash > order_cost * 2 and shares == 0:
            invest      = cash * 0.95
            shares      = invest / eff_buy
            cash       -= invest + order_cost
            avg_price   = eff_buy
            trades.append({"date": str(date), "action": "BUY", "price": price, "shares": shares})

        elif sig == "VERKAUFEN" and shares > 0:
            revenue = shares * eff_sell - order_cost
            pnl     = revenue - shares * avg_price
            cash   += revenue
            trades.append({"date": str(date), "action": "SELL", "price": price,
                            "shares": shares, "pnl": pnl})
            shares = 0.0

        equity_curve.append(cash + shares * price)

    # Letzte offene Position schließen
    if shares > 0:
        cash  += shares * _eff_price(float(aligned["Close"].iloc[-1]), "SELL", spread_pct) - order_cost
        shares = 0.0

    total_return_pct  = (cash - initial_cash) / initial_cash * 100
    buy_and_hold_pct  = (float(aligned["Close"].iloc[-1]) / float(aligned["Close"].iloc[0]) - 1) * 100

    sells    = [t for t in trades if t["action"] == "SELL"]
    wins     = [t for t in sells  if t.get("pnl", 0) > 0]
    win_rate = len(wins) / len(sells) if sells else 0.0

    eq          = np.array(equity_curve)
    peak        = np.maximum.accumulate(eq)
    dd          = (eq - peak) / np.where(peak == 0, 1, peak)
    max_dd      = float(dd.min() * 100)

    rets   = pd.Series(equity_curve).pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * math.sqrt(252)) if rets.std() > 0 else 0.0

    return BacktestResult(
        ticker=ticker,
        total_return_pct=round(total_return_pct, 2),
        buy_and_hold_pct=round(buy_and_hold_pct, 2),
        num_trades=len(trades),
        win_rate=round(win_rate, 3),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 3),
        trades=trades,
        equity_curve=equity_curve,
    )
