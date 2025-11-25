"""Utilities for loading and preparing stock price data for sequence models."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

import yfinance as yf


@dataclass
class PriceData:
    """Container for price data and derived returns."""

    prices: np.ndarray
    returns: np.ndarray


def _compute_returns(prices: np.ndarray, normalize: bool) -> np.ndarray:
    returns = np.diff(prices) / prices[:-1]
    if normalize:
        mean = returns.mean()
        std = returns.std() or 1.0
        returns = (returns - mean) / std
    return returns


def load_prices(
    csv_path: Path | str,
    date_col: str = "date",
    price_col: str = "close",
    normalize: bool = True,
) -> PriceData:
    """Load stock prices from a CSV file.

    The CSV must include a date column (parseable by pandas) and a price column.
    Data are sorted by date to ensure chronological order. Returns are computed as
    percentage change, optionally normalized to zero mean and unit variance.
    """

    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    prices = df[price_col].astype(float).to_numpy()
    returns = _compute_returns(prices, normalize)

    return PriceData(prices=prices, returns=returns)


def fetch_prices(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    normalize: bool = True,
) -> PriceData:
    """Download public price data for a ticker using Yahoo Finance.

    Args:
        ticker: Symbol to download.
        start: Optional ISO date (YYYY-MM-DD) for the first observation.
        end: Optional ISO date (YYYY-MM-DD) for the last observation (exclusive).
        interval: Sampling frequency supported by Yahoo Finance (e.g. "1d", "1h").
        normalize: Whether to standardize returns.

    Raises:
        ValueError: If no data is returned for the ticker.
    """

    df = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'")

    prices = df["Close"].astype(float).to_numpy()
    returns = _compute_returns(prices, normalize)

    return PriceData(prices=prices, returns=returns)


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
