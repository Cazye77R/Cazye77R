"""
StockMind – Automatische Strategie-Auswahl per Walk-Forward.

Ablauf je Fold:
  1. Alle Strategien × Parameter-Kombinationen auf dem TRAIN-Fenster bewerten
     (Netto-Sharpe nach Kosten).
  2. Die beste Kombination wird auf dem direkt folgenden TEST-Fenster
     eingesetzt – dort ist sie ungesehen.
Die aneinandergereihten Test-Fenster sind die ehrliche Out-of-Sample-Kurve des
"Auto"-Verfahrens. Sie wird gegen Buy & Hold verglichen, inklusive t-Statistik
der täglichen Überrenditen. Wer unter vielen Kandidaten den Besten sucht,
findet auch im Rauschen einen Gewinner – deshalb zählt nur das OOS-Ergebnis,
nie das beste In-Sample-Ergebnis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from modules.strategies import (
    STRATEGIES,
    annualized_sharpe,
    max_drawdown_pct,
    simulate,
    total_return_pct,
)

MIN_TRAIN_TRADES = (
    2  # Kandidaten ohne (fast) Handel sind auf dem Train-Fenster nicht aussagekräftig
)
MIN_OOS_DAYS = 120


@dataclass
class Fold:
    start: str
    end: str
    choice: str  # "sma_cross(fast=20, slow=50)"
    train_sharpe: float
    test_return_pct: float
    bh_return_pct: float


@dataclass
class SelectionResult:
    folds: list[Fold]
    oos_returns: pd.Series  # Auto-Strategie, aneinandergereiht
    bh_returns: pd.Series  # Buy & Hold im selben Zeitraum
    family_oos: dict[str, dict]  # je Strategie-Familie: OOS-Kennzahlen (Parameter pro Fold gewählt)
    metrics: dict
    verdict: str  # "zu_wenig_daten" | "besser" | "schlechter" | "unklar"
    current: dict = field(
        default_factory=dict
    )  # aktuelle Empfehlung (auf letztem Train-Fenster gewählt)


def _label(key: str, params: dict) -> str:
    if not params:
        return STRATEGIES[key].label
    inner = ", ".join(f"{k.rstrip('_')}={v}" for k, v in params.items())
    return f"{STRATEGIES[key].label} ({inner})"


def _candidate_returns(
    df: pd.DataFrame, cost_bps: float
) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[str, dict]]]:
    """Positionen und Netto-Renditen aller Kandidaten über die GANZE Reihe.

    Alle Strategien sind kausal (Position bei t nutzt nur Daten bis t), daher
    ist es zulässig, sie einmal über die Reihe zu rechnen und anschließend
    pro Fold zu schneiden.
    """
    pos_cols, ret_cols, meta = {}, {}, []
    close = df["Close"]
    for key, strat in STRATEGIES.items():
        for params in strat.param_sets():
            name = f"{key}|{sorted(params.items())}"
            try:
                pos = strat.positions(df, params)
            except Exception:  # defekter Kandidat darf die Auswahl nicht kippen
                continue
            pos_cols[name] = pos
            ret_cols[name] = simulate(close, pos, cost_bps)
            meta.append((key, params))
    names = list(pos_cols)
    positions = pd.DataFrame(pos_cols, columns=names)
    returns = pd.DataFrame(ret_cols, columns=names)
    return positions, returns, meta


def _score(returns: pd.Series, positions: pd.Series) -> float:
    """Train-Score: Netto-Sharpe; Kandidaten ohne Handel/Variation fliegen raus."""
    trades = int((positions.diff().abs() > 0).sum())
    if trades < MIN_TRAIN_TRADES and positions.mean() < 0.999:
        return -np.inf
    s = annualized_sharpe(returns)
    return -np.inf if math.isnan(s) else s


def _pick(
    returns: pd.DataFrame, positions: pd.DataFrame, meta, idx: slice, only: str | None = None
) -> tuple[int, float]:
    best_i, best_s = -1, -np.inf
    for i, (key, _) in enumerate(meta):
        if only is not None and key != only:
            continue
        col = returns.columns[i]
        s = _score(returns[col].iloc[idx], positions[col].iloc[idx])
        if s > best_s:
            best_i, best_s = i, s
    return best_i, best_s


def _tstat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3 or x.std() < 1e-12:
        return 0.0
    return float(x.mean() / (x.std() / math.sqrt(len(x))))


def _oos_metrics(r: pd.Series) -> dict:
    return {
        "total_return_pct": round(total_return_pct(r), 2),
        "sharpe": round(annualized_sharpe(r), 3) if len(r) > 1 else float("nan"),
        "max_drawdown_pct": round(max_drawdown_pct(r), 2),
        "days": int(len(r)),
    }


def select_strategy(
    df: pd.DataFrame,
    train_window: int = 504,
    test_window: int = 63,
    cost_bps: float = 10.0,
) -> SelectionResult:
    """
    Führt die automatische Walk-Forward-Auswahl aus.

    Args:
        df:           OHLCV-DataFrame (mind. train_window + MIN_OOS_DAYS Zeilen).
        train_window: Handelstage zum Auswählen der Strategie (Standard 2 Jahre).
        test_window:  Handelstage, die die gewählte Strategie ungesehen handelt.
        cost_bps:     Kosten je Positionswechsel in Basispunkten.
    """
    n = len(df)
    if n < train_window + MIN_OOS_DAYS:
        raise ValueError(
            f"Zu wenig Daten: {n} Handelstage, benötigt werden mind. "
            f"{train_window + MIN_OOS_DAYS} (Auswahl-Fenster {train_window} + "
            f"{MIN_OOS_DAYS} Tage Test). Längere Historie (z. B. 5y) laden."
        )

    positions, returns, meta = _candidate_returns(df, cost_bps)
    bh_col = returns.columns[[k == "buy_hold" for k, _ in meta].index(True)]
    families = sorted({k for k, _ in meta})

    folds: list[Fold] = []
    auto_pieces: list[pd.Series] = []
    bh_pieces: list[pd.Series] = []
    fam_pieces: dict[str, list[pd.Series]] = {f: [] for f in families}

    start = train_window
    while start + test_window <= n:
        train_idx = slice(start - train_window, start)
        test_idx = slice(start, start + test_window)

        for fam in families:
            fi, _ = _pick(returns, positions, meta, train_idx, only=fam)
            if fi >= 0:
                fam_pieces[fam].append(returns.iloc[test_idx, fi])

        bi, bs = _pick(returns, positions, meta, train_idx)
        if bi < 0:
            bi = returns.columns.get_loc(bh_col)
        key, params = meta[bi]
        test_ret = returns.iloc[test_idx, bi]
        bh_ret = returns[bh_col].iloc[test_idx]
        auto_pieces.append(test_ret)
        bh_pieces.append(bh_ret)
        folds.append(
            Fold(
                start=str(df.index[start].date()),
                end=str(df.index[start + test_window - 1].date()),
                choice=_label(key, params),
                train_sharpe=round(bs, 3) if np.isfinite(bs) else float("nan"),
                test_return_pct=round(total_return_pct(test_ret), 2),
                bh_return_pct=round(total_return_pct(bh_ret), 2),
            )
        )
        start += test_window

    oos = pd.concat(auto_pieces)
    bh = pd.concat(bh_pieces)

    family_oos = {}
    for fam, pieces in fam_pieces.items():
        if pieces:
            m = _oos_metrics(pd.concat(pieces))
            family_oos[fam] = {"label": STRATEGIES[fam].label, **m}

    excess = oos - bh
    t = _tstat(excess)
    auto_m, bh_m = _oos_metrics(oos), _oos_metrics(bh)
    metrics = {
        "auto": auto_m,
        "buy_hold": bh_m,
        "excess_tstat": round(t, 2),
        "folds_beating_bh": sum(1 for f in folds if f.test_return_pct > f.bh_return_pct),
        "n_folds": len(folds),
        "cost_bps": cost_bps,
    }

    if len(oos) < MIN_OOS_DAYS or len(folds) < 3:
        verdict = "zu_wenig_daten"
    elif t > 1.96:
        verdict = "besser"
    elif t < -1.96:
        verdict = "schlechter"
    else:
        verdict = "unklar"

    # Aktuelle Empfehlung: Auswahl auf dem jüngsten Train-Fenster
    last_idx = slice(n - train_window, n)
    ci, cs = _pick(returns, positions, meta, last_idx)
    current: dict = {}
    if ci >= 0:
        key, params = meta[ci]
        col = returns.columns[ci]
        current = {
            "strategy": _label(key, params),
            "key": key,
            "params": params,
            "train_sharpe": round(cs, 3),
            "position_now": "INVESTIERT" if float(positions[col].iloc[-1]) >= 0.5 else "CASH",
        }

    return SelectionResult(folds, oos, bh, family_oos, metrics, verdict, current)


VERDICT_TEXT = {
    "zu_wenig_daten": "Zu wenig Out-of-Sample-Daten für ein Urteil.",
    "besser": (
        "Die automatische Auswahl war out-of-sample signifikant besser als Buy & Hold "
        "(t > 1,96). Vergangenheit ist keine Garantie."
    ),
    "schlechter": "Die automatische Auswahl war out-of-sample signifikant schlechter als Buy & Hold.",
    "unklar": (
        "Kein belastbarer Unterschied zu Buy & Hold. Häufig ist das der Normalfall – "
        "Märkte sind schwer zu schlagen."
    ),
}
