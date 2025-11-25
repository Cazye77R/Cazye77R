"""Streamlit UI for training and forecasting stock prices with a dark theme."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import torch
from torch.utils.data import DataLoader

from .data import PriceWindowDataset, load_prices
from .inference import denormalize_returns, iterative_forecast, load_model_from_checkpoint, project_prices
from .model import ReturnLSTM


def _persist_upload(upload) -> Path:
    tmp = NamedTemporaryFile(delete=False)
    tmp.write(upload.getbuffer())
    tmp.flush()
    return Path(tmp.name)


def train_lightweight_model(
    returns: np.ndarray,
    window: int,
    epochs: int,
    lr: float,
    hidden_size: int,
    num_layers: int,
    dropout: float,
    device: str,
) -> Tuple[ReturnLSTM, float]:
    dataset = PriceWindowDataset(returns, window=window)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    model = ReturnLSTM(hidden_size=hidden_size, num_layers=num_layers, dropout=dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.MSELoss()

    model.train()
    last_loss = 0.0
    for _ in range(epochs):
        epoch_loss = 0.0
        for features, target in loader:
            features, target = features.to(device), target.to(device)
            optimizer.zero_grad()
            preds = model(features)
            loss = criterion(preds, target)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * features.size(0)
        last_loss = epoch_loss / len(loader.dataset)
    return model, last_loss


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
    st.plotly_chart(fig, use_container_width=True)


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
    st.dataframe(preview, use_container_width=True)


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
    uploaded_csv.seek(0)
    price_data = load_prices(uploaded_csv, date_col=date_col, price_col=price_col)
    uploaded_csv.seek(0)

    st.subheader("Datenvorschau")
    df_preview = pd.read_csv(uploaded_csv)
    st.dataframe(df_preview.head(), use_container_width=True)
    uploaded_csv.seek(0)

    st.subheader("Historische Preise")
    render_chart(price_data.prices, np.array([]))

    if st.button("Forecast berechnen"):
        if checkpoint_upload is not None:
            checkpoint_path = _persist_upload(checkpoint_upload)
            model, hyper = load_model_from_checkpoint(checkpoint_path)
            window = int(hyper.get("window", window))
            mean = float(hyper.get("mean", price_data.mean))
            std = float(hyper.get("std", price_data.std) or 1.0)
            uploaded_csv.seek(0)
            price_data = load_prices(
                uploaded_csv, date_col=date_col, price_col=price_col, normalize=True, normalize_stats=(mean, std)
            )
        elif enable_training:
            try:
                model, last_loss = train_lightweight_model(
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
            mean, std = price_data.mean, price_data.std
            st.toast(f"Training abgeschlossen (Loss ~ {last_loss:.4f})", icon="✅")
        else:
            st.warning("Lade einen Checkpoint oder aktiviere das Schnelltraining, um einen Forecast zu starten.")
            return

        try:
            normalized_preds = iterative_forecast(
                price_data.returns, model, window=window, steps=forecast_steps, device=device
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        denorm_preds = denormalize_returns(normalized_preds, mean=mean, std=std)
        price_projection = project_prices(price_data.prices[-1], denorm_preds)

        st.subheader("Forecast")
        cols = st.columns([1, 2])
        with cols[0]:
            render_predictions(denorm_preds, price_projection)
        with cols[1]:
            render_chart(price_data.prices, price_projection)


if __name__ == "__main__":
    main()
