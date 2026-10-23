"""Utilities for loading and preparing stock price data for sequence models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


@dataclass
class PriceData:
    """Container for price data and derived returns."""

    prices: np.ndarray
    returns: np.ndarray
    mean: float
    std: float


def compute_norm_stats(returns: np.ndarray) -> Tuple[float, float]:
    """Computes mean/std for z-score normalization, guarding degenerate inputs.

    Falls back to std=1.0 when the series is constant or contains NaN/Inf,
    so callers never silently propagate NaN normalization stats.
    """
    mean = float(np.mean(returns))
    std = float(np.std(returns))
    if not np.isfinite(mean):
        mean = 0.0
    if not np.isfinite(std) or std < 1e-12:
        std = 1.0
    return mean, std


def load_prices(
    csv_path: Path | str | IO[str] | IO[bytes],
    date_col: str = "date",
    price_col: str = "close",
    normalize: bool = True,
    normalize_stats: Tuple[float, float] | None = None,
) -> PriceData:
    """Load stock prices from a CSV file.

    The CSV must include a date column (parseable by pandas) and a price column.
    Data are sorted by date to ensure chronological order. Returns are computed as
    percentage change, optionally normalized to zero mean and unit variance.

    Raises:
        ValueError: if required columns are missing, dates can't be parsed,
            or prices contain non-finite/non-positive values.
    """

    df = pd.read_csv(csv_path)

    missing = [c for c in (date_col, price_col) if c not in df.columns]
    if missing:
        raise ValueError(
            f"Spalte(n) {missing} nicht in der CSV gefunden. Verfügbare Spalten: {list(df.columns)}"
        )

    try:
        df[date_col] = pd.to_datetime(df[date_col])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Datumsspalte '{date_col}' enthält nicht parsebare Werte: {exc}") from exc
    df = df.sort_values(date_col)

    try:
        prices = df[price_col].astype(float).to_numpy()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Preisspalte '{price_col}' enthält nicht-numerische Werte: {exc}"
        ) from exc

    if len(prices) < 2:
        raise ValueError("Mindestens 2 Kurs-Datenpunkte erforderlich.")
    if not np.all(np.isfinite(prices)):
        raise ValueError(f"Preisspalte '{price_col}' enthält NaN/Inf-Werte.")
    if np.any(prices <= 0):
        raise ValueError(
            f"Preisspalte '{price_col}' enthält Werte <= 0 (ungültig für Renditeberechnung)."
        )

    raw_returns = np.diff(prices) / prices[:-1]

    mean: float
    std: float
    if normalize:
        if normalize_stats is not None:
            mean, std = normalize_stats
        else:
            mean, std = compute_norm_stats(raw_returns)
        returns = (raw_returns - mean) / std
    else:
        returns = raw_returns
        mean, std = compute_norm_stats(raw_returns)

    return PriceData(prices=prices, returns=returns, mean=mean, std=std)


def chronological_split(
    returns: np.ndarray, train_ratio: float, window: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Splits a raw return series into train/val slices by time (no shuffling).

    Validation always covers strictly later time steps than any training
    sample. The validation slice is extended backwards by `window` samples
    so the earliest validation windows still have lookback context — that
    context is already-elapsed training-period data, not future
    information, so this introduces no leakage.

    Returns:
        (train_returns, val_returns) raw (unnormalized) return arrays.

    Raises:
        ValueError: if there isn't enough data for both a training window
            and a validation window.
    """
    if not (0.0 < train_ratio < 1.0):
        raise ValueError(f"train_ratio muss in (0, 1) liegen, nicht {train_ratio!r}.")
    if len(returns) < 2 * window + 2:
        raise ValueError(
            f"Zu wenige Datenpunkte ({len(returns)}) für Fenstergröße {window} "
            f"mit separatem Train/Val-Split (mind. {2 * window + 2} nötig)."
        )
    split_idx = int(len(returns) * train_ratio)
    split_idx = max(window + 1, min(split_idx, len(returns) - window - 1))
    train_returns = returns[:split_idx]
    val_returns = returns[split_idx - window :]
    return train_returns, val_returns


class PriceWindowDataset(Dataset[Tuple[torch.Tensor, torch.Tensor]]):
    """Sequence dataset that predicts the next return from previous returns."""

    def __init__(self, returns: Iterable[float], window: int = 30) -> None:
        values = np.array(list(returns), dtype=np.float32)
        if len(values) <= window:
            raise ValueError("Not enough data to build any windows")
        self.features = []
        self.targets = []
        for start in range(len(values) - window):
            end = start + window
            self.features.append(values[start:end])
            self.targets.append(values[end])
        self.features = np.stack(self.features)
        self.targets = np.stack(self.targets)

    def __len__(self) -> int:  # noqa: D401
        return len(self.features)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:  # noqa: D401
        feature = torch.from_numpy(self.features[idx]).unsqueeze(-1)
        target = torch.tensor(self.targets[idx], dtype=torch.float32)
        return feature, target
