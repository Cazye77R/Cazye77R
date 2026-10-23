"""Training script for the return forecasting model."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .data import (
    PriceWindowDataset,
    chronological_split,
    compute_norm_stats,
    load_prices,
    naive_baseline_loss,
    skill_score,
)
from .model import ReturnLSTM


def train(
    csv_path: Path,
    output_dir: Path,
    window: int = 30,
    batch_size: int = 64,
    epochs: int = 20,
    lr: float = 1e-3,
    hidden_size: int = 128,
    num_layers: int = 2,
    dropout: float = 0.1,
    train_ratio: float = 0.8,
    device: str | None = None,
) -> None:
    # normalize=False: we compute normalization stats from the training
    # slice only, after the chronological split below, so the validation
    # period never influences training-time statistics.
    data = load_prices(csv_path, normalize=False)
    train_returns_raw, val_returns_raw = chronological_split(data.returns, train_ratio, window)
    mean, std = compute_norm_stats(train_returns_raw)
    train_returns = (train_returns_raw - mean) / std
    val_returns = (val_returns_raw - mean) / std

    train_set = PriceWindowDataset(train_returns, window=window)
    val_set = PriceWindowDataset(val_returns, window=window)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size)

    model = ReturnLSTM(hidden_size=hidden_size, num_layers=num_layers, dropout=dropout)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.MSELoss()

    model_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model.to(model_device)

    baseline_loss = naive_baseline_loss(val_returns, window)
    print(f"Naive Baseline (Mittelwert-Prognose) val_loss={baseline_loss:.6f}")

    output_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for features, target in train_loader:
            features, target = features.to(model_device), target.to(model_device)
            optimizer.zero_grad()
            preds = model(features)
            loss = criterion(preds, target)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * features.size(0)
        train_loss = total_loss / len(train_loader.dataset)

        model.eval()
        val_loss_total = 0.0
        with torch.no_grad():
            for features, target in val_loader:
                features, target = features.to(model_device), target.to(model_device)
                preds = model(features)
                loss = criterion(preds, target)
                val_loss_total += loss.item() * features.size(0)
        val_loss = val_loss_total / len(val_loader.dataset)

        print(f"Epoch {epoch:03d} | train_loss={train_loss:.6f} | val_loss={val_loss:.6f}")

    print(f"Skill-Score vs. Baseline: {skill_score(val_loss, baseline_loss):+.1%}")

    model_path = output_dir / "return_lstm.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "hyperparameters": {
                "input_dim": 1,
                "window": window,
                "hidden_size": hidden_size,
                "num_layers": num_layers,
                "dropout": dropout,
                "train_ratio": train_ratio,
                "mean": mean,
                "std": std,
            },
        },
        model_path,
    )
    print(f"Saved model to {model_path}")


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"muss >= 1 sein, nicht {ivalue}")
    return ivalue


def _positive_float(value: str) -> float:
    fvalue = float(value)
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(f"muss > 0 sein, nicht {fvalue}")
    return fvalue


def _dropout_value(value: str) -> float:
    fvalue = float(value)
    if not (0.0 <= fvalue < 1.0):
        raise argparse.ArgumentTypeError(f"muss in [0, 1) liegen, nicht {fvalue}")
    return fvalue


def _ratio_value(value: str) -> float:
    fvalue = float(value)
    if not (0.0 < fvalue < 1.0):
        raise argparse.ArgumentTypeError(f"muss in (0, 1) liegen, nicht {fvalue}")
    return fvalue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to CSV file containing prices")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts"), help="Directory to save model checkpoints"
    )
    parser.add_argument(
        "--window", type=_positive_int, default=30, help="Number of past returns per sample"
    )
    parser.add_argument("--batch-size", type=_positive_int, default=64, help="Training batch size")
    parser.add_argument(
        "--epochs", type=_positive_int, default=20, help="Number of training epochs"
    )
    parser.add_argument("--lr", type=_positive_float, default=1e-3, help="Learning rate")
    parser.add_argument("--hidden-size", type=_positive_int, default=128, help="LSTM hidden size")
    parser.add_argument("--layers", type=_positive_int, default=2, help="Number of LSTM layers")
    parser.add_argument(
        "--dropout", type=_dropout_value, default=0.1, help="Dropout between LSTM layers"
    )
    parser.add_argument(
        "--train-ratio", type=_ratio_value, default=0.8, help="Ratio of samples for training"
    )
    parser.add_argument(
        "--device", type=str, default=None, help="Optional device override (cpu or cuda)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train(
        csv_path=args.csv_path,
        output_dir=args.output,
        window=args.window,
        batch_size=args.batch_size,
        epochs=args.epochs,
        lr=args.lr,
        hidden_size=args.hidden_size,
        num_layers=args.layers,
        dropout=args.dropout,
        train_ratio=args.train_ratio,
        device=args.device,
    )


if __name__ == "__main__":
    main()
