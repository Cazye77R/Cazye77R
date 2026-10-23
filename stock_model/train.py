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


def _run_epoch(model, loader, criterion, device, optimizer=None, clip=None) -> float:
    """One pass over ``loader``; trains if an optimizer is given, else evaluates."""
    training = optimizer is not None
    model.train(training)
    total = 0.0
    with torch.set_grad_enabled(training):
        for features, target in loader:
            features, target = features.to(device), target.to(device)
            if training:
                optimizer.zero_grad()
            loss = criterion(model(features), target)
            if training:
                loss.backward()
                if clip:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
                optimizer.step()
            total += loss.item() * features.size(0)
    return total / len(loader.dataset)


def fit_model(
    model: ReturnLSTM,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int,
    lr: float,
    device: str,
    patience: int = 5,
    weight_decay: float = 1e-4,
    clip: float = 1.0,
    on_epoch=None,
) -> tuple[float, float, int]:
    """Train with early stopping and restore the best-validation weights.

    Daily returns are mostly noise, so LSTMs overfit within a few epochs; the
    weights from the best validation epoch generalize better than the last
    ones. Also uses AdamW weight decay, gradient clipping and a plateau LR
    schedule. Returns (train_loss_at_best, best_val_loss, epochs_run).
    """
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=2)
    criterion = torch.nn.MSELoss()

    best_val = float("inf")
    best_train = float("inf")
    best_state = None
    stale = 0
    epochs_run = 0
    for epoch in range(1, epochs + 1):
        train_loss = _run_epoch(model, train_loader, criterion, device, optimizer, clip)
        val_loss = _run_epoch(model, val_loader, criterion, device)
        scheduler.step(val_loss)
        epochs_run = epoch
        if on_epoch is not None:
            on_epoch(epoch, train_loss, val_loss)
        if val_loss < best_val - 1e-9:
            best_val, best_train = val_loss, train_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return best_train, best_val, epochs_run


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
    model_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model.to(model_device)

    baseline_loss = naive_baseline_loss(val_returns, window)
    print(f"Naive Baseline (Mittelwert-Prognose) val_loss={baseline_loss:.6f}")

    output_dir.mkdir(parents=True, exist_ok=True)

    _, val_loss, epochs_run = fit_model(
        model,
        train_loader,
        val_loader,
        epochs=epochs,
        lr=lr,
        device=model_device,
        on_epoch=lambda e, tl, vl: print(
            f"Epoch {e:03d} | train_loss={tl:.6f} | val_loss={vl:.6f}"
        ),
    )
    print(f"Bestes val_loss={val_loss:.6f} (nach {epochs_run} Epochen, Early Stopping aktiv)")
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
