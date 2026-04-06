"""
StockMind – Wiederverwendbare Dashboard-Komponenten
Alle Streamlit-Widgets die in mehreren Seiten genutzt werden.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import ANALYSIS_METHODS, AVAILABLE_MODELS, DEFAULT_MODEL
from modules.easter_eggs import format_lambo, lambo_progress_bar


# ---------------------------------------------------------------------------
# Kurs-Chart
# ---------------------------------------------------------------------------

def candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    show_sma: bool = True,
    show_volume: bool = True,
) -> go.Figure:
    """Erstellt einen interaktiven Candlestick-Chart mit optionalen SMAs."""
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=ticker,
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ))

    if show_sma:
        for window, color in [(20, "#ff9800"), (50, "#2196f3")]:
            sma = df["Close"].rolling(window).mean()
            fig.add_trace(go.Scatter(
                x=df.index, y=sma,
                mode="lines",
                name=f"SMA {window}",
                line=dict(color=color, width=1.5),
            ))

    if show_volume:
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volumen",
            marker_color=colors,
            opacity=0.4,
            yaxis="y2",
        ))
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Volumen"),
        )

    fig.update_layout(
        title=f"{ticker} – Kursverlauf",
        xaxis_title="Datum",
        yaxis_title="Kurs",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def indicator_chart(df: pd.DataFrame, indicator: str) -> Optional[go.Figure]:
    """Erstellt einen Subplot-Chart für einen technischen Indikator."""
    fig = go.Figure()
    close = df["Close"]

    if indicator == "RSI":
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI", line=dict(color="#9c27b0")))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Überkauft (70)")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Überverkauft (30)")
        fig.update_layout(title="RSI (14)", yaxis=dict(range=[0, 100]))

    elif indicator == "MACD":
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist]
        fig.add_trace(go.Bar(x=df.index, y=hist, name="Histogramm", marker_color=colors))
        fig.add_trace(go.Scatter(x=df.index, y=macd, name="MACD", line=dict(color="#2196f3")))
        fig.add_trace(go.Scatter(x=df.index, y=signal, name="Signal", line=dict(color="#ff9800")))
        fig.update_layout(title="MACD (12/26/9)")

    elif indicator == "Bollinger Bands":
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        fig.add_trace(go.Scatter(x=df.index, y=close, name="Kurs", line=dict(color="white")))
        fig.add_trace(go.Scatter(x=df.index, y=upper, name="Oberes Band",
                                  line=dict(color="#ff9800", dash="dash")))
        fig.add_trace(go.Scatter(x=df.index, y=mid, name="Mittleres Band",
                                  line=dict(color="#9e9e9e")))
        fig.add_trace(go.Scatter(x=df.index, y=lower, name="Unteres Band",
                                  line=dict(color="#ff9800", dash="dash"),
                                  fill="tonexty", fillcolor="rgba(255,152,0,0.05)"))
        fig.update_layout(title="Bollinger Bands (20, 2σ)")
    else:
        return None

    fig.update_layout(template="plotly_dark", height=300)
    return fig


# ---------------------------------------------------------------------------
# Signal-Badge
# ---------------------------------------------------------------------------

def signal_badge(signal: str, confidence: float) -> None:
    """Rendert ein farbiges Signal-Badge in Streamlit."""
    colors = {
        "KAUFEN": ("#00c853", "🟢"),
        "HALTEN": ("#ff9800", "🟡"),
        "VERKAUFEN": ("#f44336", "🔴"),
    }
    color, icon = colors.get(signal, ("#9e9e9e", "⚪"))
    st.markdown(
        f"""
        <div style="
            background-color:{color}22;
            border: 2px solid {color};
            border-radius: 8px;
            padding: 12px 20px;
            text-align: center;
            font-size: 1.8rem;
            font-weight: bold;
            color: {color};
        ">
            {icon} {signal}
            <div style="font-size: 0.9rem; opacity: 0.8;">
                Konfidenz: {confidence:.0%}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Lambo-Widget
# ---------------------------------------------------------------------------

def lambo_widget(portfolio_value: float) -> None:
    """Zeigt den Lambo-Fortschrittsbalken im Dashboard."""
    pct, msg = lambo_progress_bar(portfolio_value)
    lambo_str = format_lambo(portfolio_value)

    st.markdown("### 🏎️ Lambo-O-Meter")
    st.markdown(f"Dein Portfolio entspricht {lambo_str}")
    st.progress(pct / 100, text=msg)


# ---------------------------------------------------------------------------
# Sidebar-Komponenten
# ---------------------------------------------------------------------------

def sidebar_model_selector() -> str:
    """Modell-Auswahl in der Sidebar mit Status-Anzeige."""
    from modules.model_manager import list_local_models, pull_model

    st.sidebar.markdown("### 🤖 KI-Modell")
    local_models = list_local_models()

    available = [m for m in AVAILABLE_MODELS if m in local_models]
    not_available = [m for m in AVAILABLE_MODELS if m not in local_models]

    options = available + [f"{m} (nicht installiert)" for m in not_available]
    choice = st.sidebar.selectbox(
        "Modell wählen",
        options,
        index=0 if available else 0,
        help="Nur lokal installierte Modelle können verwendet werden.",
    )

    selected = choice.split(" (")[0]

    if selected in not_available:
        if st.sidebar.button(f"⬇️ {selected} herunterladen"):
            with st.sidebar.status(f"Lade {selected}...") as status:
                try:
                    for progress in pull_model(selected):
                        st.sidebar.write(progress)
                    status.update(label=f"✅ {selected} installiert!", state="complete")
                    st.rerun()
                except ConnectionError as e:
                    st.sidebar.error(str(e))
        return DEFAULT_MODEL

    return selected


def sidebar_analysis_method() -> str:
    """Analysemethoden-Auswahl in der Sidebar."""
    return st.sidebar.selectbox(
        "Analysemethode",
        ANALYSIS_METHODS,
        index=ANALYSIS_METHODS.index("Auto (KI wählt)"),
    )


def sidebar_ticker_search() -> Optional[str]:
    """Ticker-Suche mit Autocomplete-ähnlicher Funktionalität. Unterstützt WKN, Name und Ticker."""
    from modules.data_fetcher import search_stocks, is_wkn

    st.sidebar.markdown("### 🔍 Aktie suchen")
    query = st.sidebar.text_input("Ticker, Name oder WKN", placeholder="z.B. Apple, AAPL, 716460")

    if query and len(query) >= 2:
        if is_wkn(query):
            st.sidebar.caption("🇩🇪 WKN erkannt – suche deutsches Wertpapier…")
        results = search_stocks(query)
        valid = [r for r in results if "error" not in r]
        if valid:
            def _label(r: dict) -> str:
                wkn_part = f" | WKN {r['wkn']}" if r.get("wkn") else ""
                return f"{r['symbol']} – {r['name']} ({r['exchange']}){wkn_part}"
            options = {_label(r): r["symbol"] for r in valid}
            chosen = st.sidebar.selectbox("Treffer", list(options.keys()))
            return options[chosen]
        elif results and "error" in results[0]:
            st.sidebar.warning(f"Suche fehlgeschlagen: {results[0]['error']}")

    return None


# ---------------------------------------------------------------------------
# Kennzahlen-Tabelle
# ---------------------------------------------------------------------------

def metrics_row(data: dict[str, str | float], cols: int = 4) -> None:
    """Rendert eine Zeile mit st.metric-Kacheln."""
    columns = st.columns(cols)
    for i, (label, value) in enumerate(data.items()):
        with columns[i % cols]:
            if isinstance(value, float):
                st.metric(label, f"{value:.2f}")
            else:
                st.metric(label, str(value))


def equity_curve_chart(equity: list[float], budget: float, title: str = "Equity Curve") -> go.Figure:
    """Rendert eine Equity-Kurve mit Referenzlinie."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=equity, mode="lines", name="Portfolio",
        line=dict(color="#2196f3", width=2),
        fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
    ))
    fig.add_hline(y=budget, line_dash="dash", line_color="#9e9e9e",
                  annotation_text=f"Start: {budget:.0f} €")
    fig.update_layout(
        title=title, xaxis_title="Handelstag", yaxis_title="Portfoliowert (€)",
        template="plotly_dark", height=350,
    )
    return fig
