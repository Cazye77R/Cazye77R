"""Training script for the return forecasting model."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import torch
from torch.utils.data import DataLoader, random_split

from .data import PriceWindowDataset, load_prices
from .model import ReturnLSTM


def split_dataset(dataset: PriceWindowDataset, train_ratio: float) -> Tuple[PriceWindowDataset, PriceWindowDataset]:
    train_len = int(len(dataset) * train_ratio)
    val_len = len(dataset) - train_len
    return random_split(dataset, [train_len, val_len], generator=torch.Generator().manual_seed(42))


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
    data = load_prices(csv_path)
    dataset = PriceWindowDataset(data.returns, window=window)
    train_set, val_set = split_dataset(dataset, train_ratio)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size)

    model = ReturnLSTM(hidden_size=hidden_size, num_layers=num_layers, dropout=dropout)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.MSELoss()

    model_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model.to(model_device)

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
        val_loss = 0.0
        with torch.no_grad():
            for features, target in val_loader:
                features, target = features.to(model_device), target.to(model_device)
                preds = model(features)
                loss = criterion(preds, target)
                val_loss += loss.item() * features.size(0)
        val_loss = val_loss / len(val_loader.dataset)

        print(f"Epoch {epoch:03d} | train_loss={train_loss:.6f} | val_loss={val_loss:.6f}")

    model_path = output_dir / "return_lstm.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "hyperparameters": {
                "window": window,
                "hidden_size": hidden_size,
                "num_layers": num_layers,
                "dropout": dropout,
                "train_ratio": train_ratio,
                "mean": data.mean,
                "std": data.std,
            },
        },
        model_path,
    )
    print(f"Saved model to {model_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to CSV file containing prices")
    parser.add_argument("--output", type=Path, default=Path("artifacts"), help="Directory to save model checkpoints")
    parser.add_argument("--window", type=int, default=30, help="Number of past returns per sample")
    parser.add_argument("--batch-size", type=int, default=64, help="Training batch size")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--hidden-size", type=int, default=128, help="LSTM hidden size")
    parser.add_argument("--layers", type=int, default=2, help="Number of LSTM layers")
    parser.add_argument("--dropout", type=float, default=0.1, help="Dropout between LSTM layers")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Ratio of samples for training")
    parser.add_argument("--device", type=str, default=None, help="Optional device override (cpu or cuda)")
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
