"""Neural network model definitions for forecasting returns."""
from __future__ import annotations

import torch
from torch import nn


class ReturnLSTM(nn.Module):
    """Predicts the next return based on a window of past returns."""

    def __init__(
        self,
        input_dim: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D401
        # x: [batch, seq, features]
        output, _ = self.lstm(x)
        last_hidden = output[:, -1, :]
        prediction = self.head(last_hidden).squeeze(-1)
        return prediction
