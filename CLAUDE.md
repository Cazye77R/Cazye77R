# CLAUDE.md

This file provides guidance for AI assistants working with this repository.

## Project Overview

This is a Python-based stock return forecasting project using an LSTM neural network. The codebase implements a full ML pipeline: data ingestion, model training, inference, and a Streamlit web UI. Documentation in the repo is primarily in German.

## Repository Structure

```
/
├── stock_model/          # Main Python package
│   ├── __init__.py
│   ├── model.py          # ReturnLSTM neural network definition
│   ├── data.py           # CSV loading, returns computation, dataset class
│   ├── train.py          # CLI training script
│   ├── inference.py      # Forecasting helpers and checkpoint loading
│   └── app.py            # Streamlit web UI (~500 lines)
├── .streamlit/
│   └── config.toml       # Dark theme configuration
├── requirements.txt      # Python dependencies
└── README.md             # German-language documentation
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Dependencies**: `pandas>=2.0`, `numpy>=1.24`, `torch>=2.0`, `streamlit>=1.33`, `plotly>=5.20`

No `setup.py` or `pyproject.toml` — this is a standalone project, not a distributed package.

## Key Commands

**Train a model:**
```bash
python -m stock_model.train <csv_path> \
  --window 60 \
  --batch-size 128 \
  --epochs 30 \
  --lr 5e-4 \
  --hidden-size 256 \
  --layers 2 \
  --dropout 0.2 \
  --train-ratio 0.85 \
  --output artifacts
```

**Run the web UI:**
```bash
streamlit run stock_model/app.py
```

## Data Format

Input CSVs must have `date` and `close` columns (column order is flexible). The pipeline:
1. Sorts rows by date ascending
2. Computes percentage returns from close prices
3. Applies z-score normalization (mean/std stored in checkpoint)

## Architecture

### `model.py` — `ReturnLSTM`
- LSTM with configurable `hidden_size` and `num_layers`
- Input: single-feature time series (1D returns)
- Output: single scalar (next return prediction)
- Head: Linear → LayerNorm → ReLU → Dropout → Linear

### `data.py`
- `PriceData` dataclass: holds prices, returns array, mean, std
- `load_prices(path)`: loads CSV → `PriceData`
- `PriceWindowDataset`: PyTorch `Dataset` producing sliding windows `(window, target)`

### `train.py`
- Parses CLI args, calls `load_prices`, splits train/val, runs training loop
- Saves checkpoint: `{"model_state_dict", "hyperparams", "mean", "std"}`

### `inference.py`
- `load_model_from_checkpoint(path)`: restores model + normalization stats
- `iterative_forecast(model, seed_window, steps)`: autoregressive multi-step prediction
- `denormalize_returns(preds, mean, std)`: converts normalized preds to % returns
- `project_prices(last_price, returns)`: computes future price levels
- `forecast_from_csv(csv_path, checkpoint_path, steps)`: end-to-end convenience function

### `app.py` — Streamlit UI
- Dark-themed with custom CSS; theme defined in `.streamlit/config.toml`
- Sidebar controls: window size, epochs, LR, hidden size, layers, dropout
- Accepts CSV upload and pre-trained `.pt` checkpoint upload
- Optional lightweight training within the app (1–25 epochs)
- Displays forecast chart (Plotly) and metric cards (next return, next price)

## Checkpoint Format

PyTorch `.pt` files contain:
```python
{
    "model_state_dict": ...,       # model weights
    "hyperparams": {               # architecture config
        "window": int,
        "hidden_size": int,
        "layers": int,
        "dropout": float,
    },
    "mean": float,                 # normalization mean
    "std": float,                  # normalization std
}
```

## Development Conventions

- **No tests exist** — when adding features, consider adding pytest tests under a `tests/` directory
- **No CI/CD** — no `.github/workflows/` or equivalent; all verification is manual
- **Type hints**: existing code uses them consistently; maintain this pattern
- **Docstrings**: key functions have docstrings; follow the existing style
- **No linter config**: no `.flake8`, `.pylintrc`, or `pyproject.toml`; follow PEP 8
- **Module imports**: use relative imports within the `stock_model` package

## Extending the Project

When adding features:
- New ML utilities belong in `model.py`, `data.py`, or `inference.py` as appropriate
- UI changes go in `app.py`; keep Streamlit state management via `st.session_state`
- Training changes go in `train.py`; keep CLI argument parity with `app.py` sidebar controls
- Preserve the checkpoint schema or version it to avoid breaking saved models

## Git Workflow

- Current development branch: `claude/add-claude-documentation-6WBex`
- Main branch: `main`
- No branch protection rules or PR templates configured
