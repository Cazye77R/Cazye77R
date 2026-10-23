"""
Tests für stock_model/ (PyTorch-LSTM-Forecaster).

Sichern vor allem die Fixes aus dem Code-Review gegen Rückfall ab:
- Checkpoint-Laden darf keinen Code ausführen (weights_only=True)
- Train/Val-Split ist zeitlich, Normalisierung nur aus dem Trainingsanteil
- load_prices validiert Spalten und Preise statt NaN-Verlust zu produzieren

Ohne installiertes torch werden die Tests übersprungen (das Haupt-CI-Setup
für stockmind installiert torch bewusst nicht).
"""

from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from stock_model.data import (  # noqa: E402
    PriceWindowDataset,
    chronological_split,
    compute_norm_stats,
    load_prices,
)
from stock_model.inference import (  # noqa: E402
    denormalize_returns,
    iterative_forecast,
    load_model_from_checkpoint,
    project_prices,
)
from stock_model.model import ReturnLSTM  # noqa: E402
from stock_model.train import parse_args, train  # noqa: E402


def _csv_bytes(n: int = 200, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    prices = 100 + np.cumsum(rng.normal(0.1, 1, n))
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n), "close": prices})
    return df.to_csv(index=False).encode()


# ---------------------------------------------------------------------------
# data.py
# ---------------------------------------------------------------------------


class TestLoadPrices:
    def test_basic_returns_length(self):
        data = load_prices(io.BytesIO(_csv_bytes(50)), normalize=False)
        assert len(data.prices) == 50
        assert len(data.returns) == 49

    def test_sorts_by_date(self):
        df = pd.DataFrame(
            {"date": ["2024-01-03", "2024-01-01", "2024-01-02"], "close": [3.0, 1.0, 2.0]}
        )
        data = load_prices(io.BytesIO(df.to_csv(index=False).encode()), normalize=False)
        assert list(data.prices) == [1.0, 2.0, 3.0]

    def test_missing_column_raises_valueerror(self):
        with pytest.raises(ValueError, match="nicht in der CSV"):
            load_prices(io.BytesIO(_csv_bytes()), price_col="nope")

    def test_bad_dates_raise_valueerror(self):
        df = pd.DataFrame({"date": ["kein-datum"] * 5, "close": [1.0] * 5})
        with pytest.raises(ValueError):
            load_prices(io.BytesIO(df.to_csv(index=False).encode()))

    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_prices_rejected(self, bad):
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=5), "close": [1, 2, bad, 4, 5]}
        )
        with pytest.raises(ValueError):
            load_prices(io.BytesIO(df.to_csv(index=False).encode()))

    def test_normalization_stats_override(self):
        data = load_prices(io.BytesIO(_csv_bytes()), normalize=True, normalize_stats=(0.0, 2.0))
        raw = load_prices(io.BytesIO(_csv_bytes()), normalize=False)
        np.testing.assert_allclose(data.returns, raw.returns / 2.0)


class TestNormStats:
    def test_constant_series_falls_back_to_unit_std(self):
        _, std = compute_norm_stats(np.zeros(10))
        assert std == 1.0

    def test_nan_input_never_yields_nan_stats(self):
        mean, std = compute_norm_stats(np.array([1.0, np.nan, 3.0]))
        assert np.isfinite(mean) and np.isfinite(std)


class TestChronologicalSplit:
    def test_validation_is_strictly_later_than_training(self):
        returns = np.arange(200, dtype=float)
        window = 20
        train_r, val_r = chronological_split(returns, 0.8, window)
        # Val-Targets (nach dem Kontext-Präfix) beginnen exakt nach dem Train-Ende
        assert val_r[window] == train_r[-1] + 1
        assert val_r[-1] == returns[-1]

    def test_val_windows_cover_only_post_split_targets(self):
        returns = np.arange(200, dtype=float)
        window = 20
        train_r, val_r = chronological_split(returns, 0.8, window)
        val_targets = PriceWindowDataset(val_r, window=window).targets
        assert val_targets.min() >= len(train_r)

    def test_train_slice_excludes_validation_period(self):
        returns = np.arange(200, dtype=float)
        train_r, _ = chronological_split(returns, 0.8, 20)
        assert len(train_r) < len(returns)
        assert train_r.max() < returns.max()

    def test_too_little_data_raises(self):
        with pytest.raises(ValueError):
            chronological_split(np.zeros(30), 0.8, 30)

    @pytest.mark.parametrize("ratio", [0.0, 1.0, -0.1, 1.5])
    def test_invalid_ratio_raises(self, ratio):
        with pytest.raises(ValueError):
            chronological_split(np.zeros(200), ratio, 10)


# ---------------------------------------------------------------------------
# inference.py – Sicherheit
# ---------------------------------------------------------------------------


class TestCheckpointLoading:
    def _save_valid(self, path):
        model = ReturnLSTM(hidden_size=8, num_layers=1)
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "hyperparameters": {"hidden_size": 8, "num_layers": 1, "input_dim": 1},
            },
            path,
        )

    def test_valid_checkpoint_loads_from_path_and_bytes(self, tmp_path):
        p = tmp_path / "ok.pt"
        self._save_valid(p)
        model, hyper = load_model_from_checkpoint(p)
        assert hyper["hidden_size"] == 8
        model2, _ = load_model_from_checkpoint(io.BytesIO(p.read_bytes()))
        assert isinstance(model2, ReturnLSTM)

    def test_malicious_pickle_is_not_executed(self, tmp_path):
        marker = tmp_path / "pwned.txt"

        class Evil:
            def __reduce__(self):
                return (os.system, (f"echo pwned > {marker}",))

        p = tmp_path / "evil.pt"
        torch.save({"model_state_dict": {}, "payload": Evil()}, p)
        with pytest.raises(Exception):
            load_model_from_checkpoint(p)
        assert not marker.exists(), "Checkpoint-Laden hat Code ausgeführt!"

    def test_missing_state_dict_key_rejected(self, tmp_path):
        p = tmp_path / "bad.pt"
        torch.save({"something": 1}, p)
        with pytest.raises(ValueError, match="model_state_dict"):
            load_model_from_checkpoint(p)

    def test_architecture_mismatch_rejected(self, tmp_path):
        p = tmp_path / "mismatch.pt"
        model = ReturnLSTM(hidden_size=8, num_layers=1)
        torch.save(
            {"model_state_dict": model.state_dict(), "hyperparameters": {"hidden_size": 32}}, p
        )
        with pytest.raises(ValueError):
            load_model_from_checkpoint(p)


# ---------------------------------------------------------------------------
# inference.py – Forecast-Mathematik
# ---------------------------------------------------------------------------


class TestForecastMath:
    def test_project_prices_compounds(self):
        out = project_prices(100.0, [0.1, 0.1])
        np.testing.assert_allclose(out, [110.0, 121.0], rtol=1e-5)

    def test_denormalize_roundtrip(self):
        out = denormalize_returns([0.0, 1.0], mean=0.01, std=0.02)
        np.testing.assert_allclose(out, [0.01, 0.03], rtol=1e-5)

    def test_iterative_forecast_shape_and_validation(self):
        model = ReturnLSTM(hidden_size=8, num_layers=1)
        preds = iterative_forecast(np.zeros(30), model, window=10, steps=4, device="cpu")
        assert preds.shape == (4,)
        with pytest.raises(ValueError):
            iterative_forecast(np.zeros(5), model, window=10, steps=1, device="cpu")


# ---------------------------------------------------------------------------
# train.py
# ---------------------------------------------------------------------------


class TestTrain:
    def test_train_saves_train_only_stats_and_input_dim(self, tmp_path):
        csv = tmp_path / "prices.csv"
        csv.write_bytes(_csv_bytes(300, seed=3))
        train(csv, tmp_path, window=20, batch_size=32, epochs=1, hidden_size=8, num_layers=1)
        ckpt = torch.load(tmp_path / "return_lstm.pt", map_location="cpu", weights_only=True)
        hp = ckpt["hyperparameters"]
        assert hp["input_dim"] == 1
        full = load_prices(io.BytesIO(csv.read_bytes()), normalize=False)
        # Stats stammen nur aus dem Trainingsanteil, nicht aus der ganzen Datei
        assert hp["mean"] != pytest.approx(full.mean)

    @pytest.mark.parametrize(
        "args",
        [["--epochs", "0"], ["--window", "-1"], ["--dropout", "1.5"], ["--train-ratio", "1.0"]],
    )
    def test_cli_rejects_out_of_range_args(self, args, monkeypatch):
        monkeypatch.setattr("sys.argv", ["train", "x.csv", *args])
        with pytest.raises(SystemExit):
            parse_args()


def test_naive_baseline_loss_is_mean_squared_target():
    from stock_model.data import naive_baseline_loss

    vals = np.array([0.0, 1.0, -1.0, 2.0, 0.0, 1.0], dtype=np.float32)
    # window=2 -> targets are vals[2:] = [-1, 2, 0, 1]
    assert naive_baseline_loss(vals, window=2) == pytest.approx((1 + 4 + 0 + 1) / 4)


def test_skill_score_sign_and_zero_baseline():
    from stock_model.data import skill_score

    assert skill_score(0.5, 1.0) == pytest.approx(0.5)
    assert skill_score(1.5, 1.0) < 0
    assert skill_score(0.5, 0.0) == 0.0


def _loaders(n=300, window=10):
    torch = pytest.importorskip("torch")
    from torch.utils.data import DataLoader

    from stock_model.data import PriceWindowDataset

    rng = np.random.default_rng(0)
    x = rng.normal(size=n).astype(np.float32)
    ds = PriceWindowDataset(x, window=window)
    return DataLoader(ds, batch_size=32, shuffle=True), DataLoader(ds, batch_size=32), torch


def test_fit_model_stops_early_and_restores_best_weights():
    from stock_model.model import ReturnLSTM
    from stock_model.train import fit_model

    train_l, val_l, torch = _loaders()
    model = ReturnLSTM(hidden_size=8, num_layers=1, dropout=0.0)
    seen = []
    _, best_val, epochs_run = fit_model(
        model,
        train_l,
        val_l,
        epochs=40,
        lr=0.01,
        device="cpu",
        patience=2,
        on_epoch=lambda e, tl, vl: seen.append(vl),
    )
    assert epochs_run <= 8
    assert best_val == pytest.approx(min(seen))
    # restored weights reproduce the best validation loss
    from stock_model.train import _run_epoch

    model.eval()
    again = _run_epoch(model, val_l, torch.nn.MSELoss(), "cpu")
    assert again == pytest.approx(best_val, rel=1e-4)
