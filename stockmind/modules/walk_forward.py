"""
StockMind – Walk-Forward-Backtest

Rollierende Train/Test-Fenster über einen OHLCV-DataFrame.
Die Strategie-Funktion erhält Train- und Test-Slice und gibt
eine Signal-Series zurück; die Funktion aggregiert Metriken
über alle Folds.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def walk_forward_backtest(
    df: pd.DataFrame,
    strategy_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.Series],
    train_window: int = 252,
    test_window: int = 63,
    step: int = 21,
) -> dict:
    """
    Walk-Forward-Backtest mit rollierenden Fenstern.

    Der DataFrame wird in nicht-überlappende Test-Fenster aufgeteilt,
    jedem vorangeht ein Train-Fenster. Die Strategie-Funktion wird pro
    Fold aufgerufen und gibt eine Signal-Series zurück (1=Long, 0=Flat,
    -1=Short oder binär 0/1). Aus den Test-Renditen werden
    Fold-Metriken berechnet und am Ende aggregiert.

    Args:
        df:            OHLCV-DataFrame, Index = DatetimeIndex, muss
                       mindestens train_window + test_window Zeilen haben.
        strategy_fn:   Callable(train_df, test_df) -> pd.Series mit
                       gleichem Index wie test_df.
        train_window:  Anzahl Handelstage für Training (Standard: 252 ≈ 1 Jahr).
        test_window:   Größe des Test-Fensters in Tagen (Standard: 63 ≈ 1 Quartal).
        step:          Schrittweite zwischen Folds (Standard: 21 ≈ 1 Monat).

    Returns:
        dict mit:
          - "fold_results":      list[dict] – pro Fold: start, end,
                                 total_return, sharpe, n_trades
          - "equity_curve":      pd.Series – aggregierte Equity-Kurve
                                 über alle Test-Fenster
          - "total_return":      float – kumulierter Return über alle Folds
          - "mean_sharpe":       float – Sharpe-Mittelwert
          - "n_folds":           int
          - "n_folds_profitable":int – Folds mit positivem Return
    """
    n = len(df)
    min_required = train_window + test_window
    if n < min_required:
        raise ValueError(
            f"DataFrame hat nur {n} Zeilen, benötigt mind. "
            f"{min_required} (train_window + test_window)."
        )

    fold_results: list[dict] = []
    all_equity_pieces: list[pd.Series] = []

    test_start = train_window
    while test_start + test_window <= n:
        train_df = df.iloc[test_start - train_window : test_start]
        test_df  = df.iloc[test_start : test_start + test_window]

        try:
            signals = strategy_fn(train_df, test_df)
        except Exception as exc:
            fold_results.append({
                "start":        str(test_df.index[0].date()),
                "end":          str(test_df.index[-1].date()),
                "total_return": 0.0,
                "sharpe":       float("nan"),
                "n_trades":     0,
                "error":        str(exc),
            })
            test_start += step
            continue

        # Sicherstellen, dass Signals denselben Index wie test_df haben
        signals = signals.reindex(test_df.index).fillna(0)

        daily_returns = test_df["Close"].pct_change().fillna(0)
        strat_returns = daily_returns * signals.shift(1).fillna(0)

        equity = (1 + strat_returns).cumprod()
        fold_total_return = float(equity.iloc[-1]) - 1.0

        sharpe = _fold_sharpe(strat_returns)
        n_trades = int((signals.diff().abs() > 0).sum())

        fold_results.append({
            "start":        str(test_df.index[0].date()),
            "end":          str(test_df.index[-1].date()),
            "total_return": round(fold_total_return * 100, 2),
            "sharpe":       round(sharpe, 3),
            "n_trades":     n_trades,
        })
        all_equity_pieces.append(equity)

        test_start += step

    # Aggregierte Equity-Kurve: Folds sequenziell verketten
    if all_equity_pieces:
        # Auf kumulierten Gesamtwert renormieren
        scale = 1.0
        renormed_pieces: list[pd.Series] = []
        for piece in all_equity_pieces:
            renormed_pieces.append(piece * scale)
            scale *= float(piece.iloc[-1])
        equity_curve = pd.concat(renormed_pieces)
    else:
        equity_curve = pd.Series(dtype=float)

    total_returns = [f["total_return"] for f in fold_results if "error" not in f]
    sharpes       = [f["sharpe"] for f in fold_results if not np.isnan(f.get("sharpe", float("nan")))]

    return {
        "fold_results":       fold_results,
        "equity_curve":       equity_curve,
        "total_return":       round(float(np.prod([1 + r / 100 for r in total_returns]) - 1) * 100, 2)
                              if total_returns else 0.0,
        "mean_sharpe":        round(float(np.mean(sharpes)), 3) if sharpes else float("nan"),
        "n_folds":            len(fold_results),
        "n_folds_profitable": sum(1 for r in total_returns if r > 0),
    }


def _fold_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Annualisierter Sharpe-Ratio (Risk-Free = 0) für eine Rendite-Series."""
    if len(returns) < 2:
        return float("nan")
    std = float(returns.std())
    if std < 1e-12:
        return float("nan")
    return float(returns.mean() / std * np.sqrt(periods_per_year))
