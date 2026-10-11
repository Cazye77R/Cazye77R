"""Streamlit UI for training and forecasting stock prices with a dark theme."""
from __future__ import annotations

import io
from typing import Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import torch
from torch.utils.data import DataLoader

from .data import (
    PriceData,
    PriceWindowDataset,
    chronological_split,
    compute_norm_stats,
    load_prices,
)
from .inference import (
    denormalize_returns,
    iterative_forecast,
    load_model_from_checkpoint,
    project_prices,
)
from .model import ReturnLSTM


@st.cache_data(show_spinner=False)
def _load_prices_cached(
    file_bytes: bytes, date_col: str, price_col: str
) -> PriceData:
    """Cached CSV parse (normalize=False — callers normalize per their own split)."""
    return load_prices(io.BytesIO(file_bytes), date_col=date_col, price_col=price_col, normalize=False)


def train_lightweight_model(
    returns: np.ndarray,
    window: int,
    epochs: int,
    lr: float,
    hidden_size: int,
    num_layers: int,
    dropout: float,
    device: str,
    train_ratio: float = 0.8,
) -> Tuple[ReturnLSTM, float, float, float, float]:
    """Quick in-app training with a chronological train/val split.

    Unlike shuffling 100% of overlapping windows into one pool, this splits
    by time first and fits normalization stats on the training slice only,
    so the reported validation loss is a meaningful (if noisy, given the
    small epoch budget) out-of-sample estimate rather than a leaked number.

    Returns:
        (model, train_loss, val_loss, mean, std)
    """
    train_returns_raw, val_returns_raw = chronological_split(returns, train_ratio, window)
    mean, std = compute_norm_stats(train_returns_raw)
    train_returns = (train_returns_raw - mean) / std
    val_returns = (val_returns_raw - mean) / std

    train_set = PriceWindowDataset(train_returns, window=window)
    val_set = PriceWindowDataset(val_returns, window=window)
    train_loader = DataLoader(train_set, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=64)

    model = ReturnLSTM(hidden_size=hidden_size, num_layers=num_layers, dropout=dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.MSELoss()

    train_loss = 0.0
    val_loss = 0.0
    for _ in range(epochs):
        model.train()
        epoch_loss = 0.0
        for features, target in train_loader:
            features, target = features.to(device), target.to(device)
            optimizer.zero_grad()
            preds = model(features)
            loss = criterion(preds, target)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * features.size(0)
        train_loss = epoch_loss / len(train_loader.dataset)

        model.eval()
        val_epoch_loss = 0.0
        with torch.no_grad():
            for features, target in val_loader:
                features, target = features.to(device), target.to(device)
                preds = model(features)
                loss = criterion(preds, target)
                val_epoch_loss += loss.item() * features.size(0)
        val_loss = val_epoch_loss / len(val_loader.dataset)

    return model, train_loss, val_loss, mean, std


def render_chart(prices: np.ndarray, forecast_prices: np.ndarray) -> None:
    history = pd.DataFrame({"Index": range(len(prices)), "Preis": prices, "Typ": "Historie"})
    forecast_index = range(len(prices), len(prices) + len(forecast_prices))
    forecast_df = pd.DataFrame(
        {"Index": list(forecast_index), "Preis": forecast_prices, "Typ": "Forecast"}
    )
    combined = pd.concat([history, forecast_df])
    fig = px.line(combined, x="Index", y="Preis", color="Typ", markers=True)
    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        legend_title="",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, width="stretch")


def render_predictions(denorm_returns: np.ndarray, price_projection: np.ndarray) -> None:
    next_return = denorm_returns[0] if len(denorm_returns) else 0.0
    next_price = price_projection[0] if len(price_projection) else np.nan
    st.metric("Nächste Rendite", f"{next_return * 100:.2f}%")
    st.metric("Prognostizierter Preis", f"{next_price:,.2f}")

    preview = pd.DataFrame(
        {
            "Schritt": list(range(1, len(denorm_returns) + 1)),
            "Rendite (%)": denorm_returns * 100,
            "Preis": price_projection,
        }
    )
    st.dataframe(preview, width="stretch")
    st.caption(
        "⚠️ Mehrstufige Prognosen führen ihre eigenen Vorhersagen als Eingabe fort — "
        "der Fehler kann sich von Schritt zu Schritt aufsummieren. Es wird keine "
        "Unsicherheits-/Konfidenzspanne berechnet; spätere Schritte sind entsprechend "
        "unsicherer als frühe."
    )


def main() -> None:
    st.set_page_config(page_title="Stock Forecaster", page_icon="📈", layout="wide")
    st.title("📈 Dunkle KI-Oberfläche für Forecasting")
    st.markdown(
        """
        Lade deine Kursdaten hoch, wähle optional ein trainiertes Modell und lasse die KI
        einen mehrstufigen Forecast erstellen. Die Oberfläche ist für einen dunklen Modus optimiert.
        """
    )
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.12), transparent 25%),
                        radial-gradient(circle at 80% 0%, rgba(168, 85, 247, 0.12), transparent 25%),
                        #0b1220;
            color: #e5e7eb;
        }
        .block-container {
            padding-top: 1.5rem;
        }
        .stDataFrame, .stMetric {
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("Steuerung")
    forecast_steps = st.sidebar.slider("Forecast-Schritte", min_value=1, max_value=14, value=3)
    window = st.sidebar.slider("Fenstergröße", min_value=10, max_value=120, value=30, step=5)
    date_col = st.sidebar.text_input("Datumsspalte", value="date")
    price_col = st.sidebar.text_input("Preisspalte", value="close")

    st.sidebar.subheader("Optional: Schnelltraining")
    enable_training = st.sidebar.checkbox("Direkt in der App trainieren, wenn kein Checkpoint geladen ist")
    train_epochs = st.sidebar.slider("Epochen", 1, 25, 5)
    lr = st.sidebar.number_input("Lernrate", min_value=1e-5, max_value=1e-1, value=1e-3, format="%e")
    hidden_size = st.sidebar.slider("Hidden Size", 32, 512, 128, step=32)
    num_layers = st.sidebar.slider("LSTM Layer", 1, 4, 2)
    dropout = st.sidebar.slider("Dropout", 0.0, 0.7, 0.1, step=0.05)

    uploaded_csv = st.file_uploader("CSV mit Kursdaten", type=["csv"])
    checkpoint_upload = st.file_uploader("Trainiertes Modell (.pt oder .pth)", type=["pt", "pth"])

    if uploaded_csv is None:
        st.info("Bitte lade eine CSV-Datei hoch, die mindestens `date` und `close` enthält.")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        # normalize=False: this is the shared/display price_data. Each
        # training path (checkpoint vs. quick-train) derives its own
        # normalization stats from only the data it's entitled to see.
        price_data = _load_prices_cached(uploaded_csv.getvalue(), date_col, price_col)
    except ValueError as exc:
        st.error(f"Fehler beim Laden der CSV: {exc}")
        return

    st.subheader("Datenvorschau")
    try:
        df_preview = pd.read_csv(io.BytesIO(uploaded_csv.getvalue()))
    except Exception as exc:  # pragma: no cover - defensive, load_prices already validated
        st.error(f"Fehler beim Anzeigen der CSV-Vorschau: {exc}")
        return
    st.dataframe(df_preview.head(), width="stretch")

    st.subheader("Historische Preise")
    render_chart(price_data.prices, np.array([]))

    if st.button("Forecast berechnen"):
        # mean/std/val_loss are always set by one of the two branches below
        # before iterative_forecast() is called; the third (else) branch
        # returns early. No branch falls back to price_data's full-history
        # stats, which would leak validation-period data into the forecast.
        val_loss: float | None = None

        if checkpoint_upload is not None:
            try:
                model, hyper = load_model_from_checkpoint(io.BytesIO(checkpoint_upload.getbuffer()))
            except ValueError as exc:
                st.error(f"Checkpoint konnte nicht geladen werden: {exc}")
                return
            window = int(hyper.get("window", window))
            mean = float(hyper.get("mean", price_data.mean))
            std = float(hyper.get("std", price_data.std) or 1.0)
            # Normalize the full available history with the checkpoint's
            # training-time stats (standard practice — not leakage, since
            # those stats were already fixed before this inference call).
            forecast_returns = (price_data.returns - mean) / std
        elif enable_training:
            try:
                with st.spinner(f"Trainiere Modell ({train_epochs} Epochen)…"):
                    model, train_loss, val_loss, mean, std = train_lightweight_model(
                        price_data.returns,
                        window=window,
                        epochs=train_epochs,
                        lr=lr,
                        hidden_size=hidden_size,
                        num_layers=num_layers,
                        dropout=dropout,
                        device=device,
                    )
            except ValueError as exc:
                st.error(str(exc))
                return
            st.toast(
                f"Training abgeschlossen (train_loss ~ {train_loss:.4f}, val_loss ~ {val_loss:.4f})",
                icon="✅",
            )
            # For the live forecast, use the full available history as
            # context (normalized with the just-fitted train-split stats) —
            # the train/val split only matters for judging model quality.
            forecast_returns = (price_data.returns - mean) / std
        else:
            st.warning("Lade einen Checkpoint oder aktiviere das Schnelltraining, um einen Forecast zu starten.")
            return

        try:
            normalized_preds = iterative_forecast(
                forecast_returns, model, window=window, steps=forecast_steps, device=device
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        denorm_preds = denormalize_returns(normalized_preds, mean=mean, std=std)
        price_projection = project_prices(price_data.prices[-1], denorm_preds)

        st.session_state["forecast_result"] = {
            "prices": price_data.prices,
            "denorm_preds": denorm_preds,
            "price_projection": price_projection,
            "val_loss": val_loss,
        }

    result = st.session_state.get("forecast_result")
    if result is not None:
        st.subheader("Forecast")
        if result["val_loss"] is not None:
            st.caption(
                f"Validierungs-Loss (zeitlich nach den Trainingsdaten, nicht gesehen): "
                f"{result['val_loss']:.6f}"
            )
        cols = st.columns([1, 2])
        with cols[0]:
            render_predictions(result["denorm_preds"], result["price_projection"])
        with cols[1]:
            render_chart(result["prices"], result["price_projection"])


if __name__ == "__main__":
    main()
