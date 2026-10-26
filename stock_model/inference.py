"""Inference helpers for return forecasting and price projection."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Iterable, Tuple

import numpy as np
import torch

from .model import ReturnLSTM


def load_model_from_checkpoint(
    checkpoint_source: Path | str | IO[bytes],
) -> Tuple[ReturnLSTM, dict]:
    """Load a trained :class:`ReturnLSTM` and its hyperparameters.

    Accepts a filesystem path or an in-memory file-like object (e.g. the
    bytes of an uploaded file), so callers never have to persist untrusted
    uploads to disk.

    Security note: loaded with ``weights_only=True`` so the checkpoint can
    only contain tensors/plain Python containers, not arbitrary pickled
    objects — a checkpoint is user-uploadable data in the Streamlit UI and
    must never be able to execute code on load.

    Raises:
        ValueError: if the checkpoint is missing required keys or its
            weights don't match the model architecture.
    """

    checkpoint = torch.load(checkpoint_source, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError("Ungültige Checkpoint-Datei: Schlüssel 'model_state_dict' fehlt.")

    hyperparameters = checkpoint.get("hyperparameters", {})
    model = ReturnLSTM(
        input_dim=hyperparameters.get("input_dim", 1),
        hidden_size=hyperparameters.get("hidden_size", 64),
        num_layers=hyperparameters.get("num_layers", 2),
        dropout=hyperparameters.get("dropout", 0.1),
    )
    try:
        model.load_state_dict(checkpoint["model_state_dict"])
    except RuntimeError as exc:
        raise ValueError(f"Checkpoint-Gewichte passen nicht zum Modell-Aufbau: {exc}") from exc
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
