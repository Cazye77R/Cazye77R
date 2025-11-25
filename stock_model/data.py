"""Utilities for loading and preparing stock price data for sequence models."""
from __future__ import annotations

from dataclasses import dataclass
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
    """

    df = pd.read_csv(csv_path)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    prices = df[price_col].astype(float).to_numpy()
    raw_returns = np.diff(prices) / prices[:-1]

    mean: float
    std: float
    if normalize:
        if normalize_stats is not None:
            mean, std = normalize_stats
        else:
            mean = float(raw_returns.mean())
            std = float(raw_returns.std() or 1.0)
        returns = (raw_returns - mean) / std
    else:
        returns = raw_returns
        mean = float(raw_returns.mean())
        std = float(raw_returns.std() or 1.0)

    return PriceData(prices=prices, returns=returns, mean=mean, std=std)


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
