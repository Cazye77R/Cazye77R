"""Inference helpers for return forecasting and price projection."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import torch

from .data import PriceData, load_prices
from .model import ReturnLSTM


def load_model_from_checkpoint(checkpoint_path: Path | str) -> Tuple[ReturnLSTM, dict]:
    """Load a trained :class:`ReturnLSTM` and its hyperparameters."""

    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    hyperparameters = checkpoint.get("hyperparameters", {})
    model = ReturnLSTM(
        input_dim=1,
        hidden_size=hyperparameters.get("hidden_size", 64),
        num_layers=hyperparameters.get("num_layers", 2),
        dropout=hyperparameters.get("dropout", 0.1),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, hyperparameters


def iterative_forecast(
    returns: Iterable[float],
    model: ReturnLSTM,
    window: int,
    steps: int = 1,
    device: str | None = None,
) -> np.ndarray:
    """Generate ``steps`` normalized return forecasts by feeding back predictions."""

    values = np.asarray(list(returns), dtype=np.float32)
    if len(values) < window:
        raise ValueError("Not enough data to build a forecast window")

    model_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(model_device)

    current = torch.from_numpy(values[-window:]).unsqueeze(0).unsqueeze(-1).to(model_device)
    predictions = []

    model.eval()
    for _ in range(steps):
        with torch.no_grad():
            pred = model(current).squeeze().item()
        predictions.append(pred)
        next_val = torch.tensor([[pred]], device=model_device)
        current = torch.cat([current.squeeze(0), next_val], dim=0)[-window:].unsqueeze(0)

    return np.array(predictions, dtype=np.float32)


def denormalize_returns(predictions: Iterable[float], mean: float, std: float) -> np.ndarray:
    """Convert normalized return predictions back into percentage returns."""

    return np.array(predictions, dtype=np.float32) * std + mean


def project_prices(last_price: float, returns: Iterable[float]) -> np.ndarray:
    """Compute price levels from a starting price and predicted returns."""

    price = float(last_price)
    prices = []
    for ret in returns:
        price *= 1 + ret
        prices.append(price)
    return np.array(prices, dtype=np.float32)


def forecast_from_csv(
    csv_path: Path | str,
    checkpoint_path: Path | str,
    steps: int = 1,
    device: str | None = None,
) -> Tuple[np.ndarray, np.ndarray, PriceData]:
    """Load data and checkpoint to forecast normalized returns and prices."""

    model, hyperparameters = load_model_from_checkpoint(checkpoint_path)
    window = int(hyperparameters.get("window", 30))
    mean = float(hyperparameters.get("mean", 0.0))
    std = float(hyperparameters.get("std", 1.0) or 1.0)

    price_data = load_prices(csv_path, normalize=True, normalize_stats=(mean, std))
    normalized_preds = iterative_forecast(price_data.returns, model, window=window, steps=steps, device=device)
    denorm_preds = denormalize_returns(normalized_preds, mean=mean, std=std)
    price_projection = project_prices(price_data.prices[-1], denorm_preds)
    return normalized_preds, price_projection, price_data
