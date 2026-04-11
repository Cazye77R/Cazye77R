"""
StockMind – Streamlit Dashboard  (Bloomberg / Trading-Terminal Style)
"""
from __future__ import annotations

import math
import os
import random
import sys
import time
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    APP_TITLE, APP_ICON, APP_VERSION,
    ANALYSIS_METHODS, DEFAULT_BUDGET_EUR, DEFAULT_PERIOD,
    LAMBO_PRICE_EUR, ORDER_COST_EUR, SPREAD_PERCENT, AVAILABLE_MODELS,
    EXPLORATION_CONSTANT, ENABLE_EASTER_EGGS, CACHE_TTL_HOURS,
)
from modules.model_manager import (
    MODEL_DESCRIPTIONS, is_ollama_running, get_ollama_status,
    get_available_models, get_available_models_with_info, download_model,
    analyze_stock,
)
from modules.data_fetcher import (
    search_stocks, fetch_ohlcv, fetch_info, is_valid_ticker,
)
from modules.trainer import StockTrainer, load_state, load_model, train, list_trained_stocks
from modules.predictor import predict, build_context_string, SIGNAL_FUNCTIONS
from modules.backtester import (
    PaperTrader, lambo_value, lambo_display, lambo_progress, backtest_signals,
)
from modules.easter_eggs import (
    check_easter_egg, get_currency_display, get_trade_count_egg,
    CURRENCIES, CURRENCY_UNLOCK_CLICKS, CONFETTI_MARKER,
)

# ─────────────────────────────────────────────────────────────────────────────
# Page config – MUSS als erster Streamlit-Aufruf stehen
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# @st.cache_data – vermeidet redundante HTTP/IO-Calls bei jedem Rerun
# Alle externen API-Aufrufe laufen garantiert im Hauptthread (kein Context-Loss).
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _check_ollama() -> bool:
    """Gecachter Ollama-Verbindungscheck (60 s TTL)."""
    return is_ollama_running()


@st.cache_data(ttl=60, show_spinner=False)
def _ollama_status() -> dict:
    """Gecachter erweiterter Ollama-Status (60 s TTL)."""
    return get_ollama_status()


@st.cache_data(ttl=60, show_spinner=False)
def _models_list() -> list:
    """Gecachte Liste installierter Modell-Namen (60 s TTL)."""
    return get_available_models()


@st.cache_data(ttl=60, show_spinner=False)
def _models_info() -> list:
    """Gecachte Modell-Infos inkl. Größe (60 s TTL)."""
    return get_available_models_with_info()


@st.cache_data(ttl=300, show_spinner=False)
def _ohlcv(ticker: str, period: str) -> pd.DataFrame:
    """Gecachte OHLCV-Daten (5 min TTL, zusätzlich zum Parquet-Datei-Cache)."""
    return fetch_ohlcv(ticker, period=period)


@st.cache_data(ttl=3600, show_spinner=False)
def _info(ticker: str) -> dict:
    """Gecachte Stammdaten/Metadaten (1 h TTL)."""
    return fetch_info(ticker)


@st.cache_data(ttl=120, show_spinner=False)
def _search(query: str) -> list:
    """Gecachte Suchergebnisse (2 min TTL)."""
    return search_stocks(query)

# ─────────────────────────────────────────────────────────────────────────────
# Bloomberg / Trading-Terminal CSS
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
<style>
/* ── Global ────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container          { background-color: #0d1117 !important; color: #c9d1d9; }

[data-testid="stSidebar"]       { background-color: #0a0e14 !important;
                                   border-right: 1px solid #1c2128 !important; }

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar              { width: 6px; height: 6px; }
::-webkit-scrollbar-track        { background: #0d1117; }
::-webkit-scrollbar-thumb        { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover  { background: #00ff88; }

/* ── Tabs ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { background: #0a0e14 !important;
                                     border-bottom: 1px solid #1c2128; gap: 2px; }
.stTabs [data-baseweb="tab"]      { background: transparent !important;
                                     color: #8b949e !important;
                                     border-radius: 4px 4px 0 0;
                                     font-family: 'IBM Plex Mono', monospace;
                                     font-size: 13px; padding: 8px 16px; }
.stTabs [aria-selected="true"]    { background: #161b22 !important;
                                     color: #00ff88 !important;
                                     border-top: 2px solid #00ff88 !important; }

/* ── Buttons ───────────────────────────────────────────────────── */
.stButton > button {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace; font-size: 12px;
    transition: all 0.2s;
}
.stButton > button:hover {
    border-color: #00ff88; color: #00ff88;
    box-shadow: 0 0 8px rgba(0,255,136,0.3);
}
.stButton > button[kind="primary"] {
    background: #00ff88; color: #0d1117; border-color: #00ff88;
    font-weight: 700;
}
.stButton > button[kind="primary"]:hover {
    background: #00cc6a; box-shadow: 0 0 12px rgba(0,255,136,0.5);
}

/* ── Inputs ────────────────────────────────────────────────────── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: #0d1117 !important; color: #c9d1d9 !important;
    border: 1px solid #30363d !important; border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace;
}
.stTextInput input:focus { border-color: #00ff88 !important;
                            box-shadow: 0 0 6px rgba(0,255,136,0.3) !important; }

/* ── Metrics ───────────────────────────────────────────────────── */
[data-testid="stMetric"]         { background: #161b22; border: 1px solid #1c2128;
                                     border-radius: 6px; padding: 12px !important; }
[data-testid="stMetricValue"]    { color: #c9d1d9 !important;
                                     font-family: 'IBM Plex Mono', monospace; }
[data-testid="stMetricDelta"]    { font-family: 'IBM Plex Mono', monospace; }

/* ── Progress bar ──────────────────────────────────────────────── */
.stProgress > div > div { background: #00ff88 !important; }

/* ── Dataframe ─────────────────────────────────────────────────── */
[data-testid="stDataFrame"]      { border: 1px solid #1c2128; border-radius: 4px; }

/* ── Divider ───────────────────────────────────────────────────── */
hr { border-color: #1c2128; }

/* ── Custom components ─────────────────────────────────────────── */
.sm-card {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 6px; padding: 16px; margin: 4px 0;
}
.sm-card-accent {
    background: #0d2b1a; border: 1px solid #00ff88;
    border-radius: 6px; padding: 16px; margin: 4px 0;
}
.sm-header {
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; border-bottom: 1px solid #1c2128;
    padding-bottom: 6px; margin-bottom: 12px;
}
.sm-big-num {
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 40px; font-weight: 700; line-height: 1;
    text-shadow: 0 0 20px rgba(0,255,136,0.4);
}
.sm-label {
    color: #8b949e; font-family: 'IBM Plex Mono', monospace;
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
}
.sm-badge-up {
    display: inline-block; background: #0d2b1a; color: #00ff88;
    border: 1px solid #00ff88; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-badge-down {
    display: inline-block; background: #2a0d0d; color: #ff4444;
    border: 1px solid #ff4444; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-badge-neutral {
    display: inline-block; background: #1c2128; color: #8b949e;
    border: 1px solid #30363d; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-online  { color: #00ff88; font-weight: 700; }
.sm-offline { color: #ff4444; font-weight: 700; }
.sm-quote {
    background: #0a0e14; border-left: 3px solid #00ff88;
    padding: 10px 14px; border-radius: 0 4px 4px 0;
    color: #8b949e; font-style: italic; font-size: 14px;
    margin: 8px 0;
}
.sm-model-row {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; border-bottom: 1px solid #1c2128;
}
.sm-active-badge {
    background: #0d2b1a; color: #00ff88; border: 1px solid #00ff88;
    border-radius: 3px; padding: 1px 6px; font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
}

/* ── Ticker tape animation ─────────────────────────────────────── */
@keyframes ticker {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.sm-ticker {
    overflow: hidden; background: #0a0e14;
    border: 1px solid #1c2128; border-radius: 4px;
    padding: 6px 0; white-space: nowrap;
}
.sm-ticker-inner {
    display: inline-block;
    animation: ticker 25s linear infinite;
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; letter-spacing: 1px;
}

/* ── Pulse animation (AI thinking) ────────────────────────────── */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.2; }
}
.sm-pulse {
    animation: pulse 1.5s infinite;
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
}
.sm-scan-line {
    height: 2px; background: linear-gradient(90deg, transparent, #00ff88, transparent);
    animation: scan 2s linear infinite;
}
@keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
</style>
"""

def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

_inject_css()

# ─────────────────────────────────────────────────────────────────────────────
# Finance-Zitate & Ticker-Tape
# ─────────────────────────────────────────────────────────────────────────────
_QUOTES = [
    "Sei gierig, wenn andere ängstlich sind. – Warren Buffett",
    "Die Börse ist ein Instrument um Geld von Ungeduldigen zu Geduldigen zu transferieren. – W. Buffett",
    "Kurzfristig ist die Börse eine Abstimmungsmaschine, langfristig eine Waage. – Benjamin Graham",
    "Der Markt kann länger irrational bleiben als du solvent. – J. M. Keynes",
    "Kaufe, wenn alle verkaufen. Verkaufe, wenn alle kaufen. – J. Paul Getty",
    "Risiko kommt daher, dass man nicht weiß, was man tut. – Warren Buffett",
    "Der beste Zeitpunkt zu investieren war gestern. Der zweitbeste ist heute.",
    "Diversifikation ist Schutz gegen Unwissenheit. – Warren Buffett",
    "In der Investition ist das, was komfortabel ist, selten profitabel. – Robert Arnott",
    "Zeit im Markt schlägt das Timing des Marktes.",
    "Der Markt ist ein Ort, wo Wertpapiere von Aktiven zu Geduldigen wandern. – Nicolas Darvas",
    "Vier Worte, die Investoren viel Geld gekostet haben: Diesmal ist es anders. – Sir John Templeton",
]

_TICKER_WORDS = (
    "KAUFEN \u2022 HALTEN \u2022 VERKAUFEN \u2022 RSI \u2022 MACD \u2022 BOLLINGER \u2022 "
    "KI ANALYSIERT \u2022 MUSTER ERKANNT \u2022 SIGNAL \u2022 TREND \u2022 VOLUMEN \u2022 "
    "SUPPORT \u2022 RESISTANCE \u2022 MOMENTUM \u2022 DIVERGENZ \u2022 BREAKOUT \u2022 "
)

def _ticker_html() -> str:
    tape = _TICKER_WORDS * 5
    return (
        f'<div class="sm-ticker"><span class="sm-ticker-inner">{tape}</span></div>'
    )

def _quote_html(quote: str) -> str:
    return f'<div class="sm-quote">"{quote}"</div>'

def _signal_badge_html(signal: str) -> str:
    mapping = {
        "UP": "sm-badge-up", "KAUFEN": "sm-badge-up", "BUY": "sm-badge-up",
        "DOWN": "sm-badge-down", "VERKAUFEN": "sm-badge-down", "SELL": "sm-badge-down",
        "NEUTRAL": "sm-badge-neutral", "HALTEN": "sm-badge-neutral", "HOLD": "sm-badge-neutral",
    }
    cls = mapping.get(signal.upper(), "sm-badge-neutral")
    return f'<span class="{cls}">{signal}</span>'

def _section(label: str) -> None:
    st.markdown(f'<div class="sm-header">{label}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Startup-Health-Check: Verzeichnisse + Ollama-Status
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_data_dirs() -> None:
    """Erstellt fehlende Daten-Ordner beim ersten Start."""
    for d in ["data", "data/cache", "data/training_state", "data/portfolio", "data/logs"]:
        os.makedirs(d, exist_ok=True)


def _startup_check() -> None:
    """
    Beim App-Start: Verzeichnisse anlegen, Ollama pruefen, Onboarding anzeigen.
    Wird einmal pro Session ausgefuehrt (session_state.startup_done).
    """
    if st.session_state.get("startup_done"):
        return
    _ensure_data_dirs()

    ollama_ok = _check_ollama()
    has_models = False
    if ollama_ok:
        try:
            has_models = len(_models_list()) > 0
        except Exception:
            pass

    if not ollama_ok:
        st.info(
            "Willkommen bei StockMind! "
            "Ollama ist nicht erreichbar – starte es mit: "
            "ollama serve && ollama pull llama3. "
            "Marktdaten und Charts funktionieren auch ohne Ollama.",
            icon="🚀",
        )
    elif not has_models:
        st.info(
            "Kein Modell installiert – "
            "oeffne den Tab Modell-Manager und lade ein Modell herunter (Empfehlung: llama3).",
            icon="📦",
        )

    st.session_state.startup_done = True

def _init_session() -> None:
    defaults: dict = {
        "ticker": "",
        "df": None,
        "info": {},
        "prediction": None,
        "analysis_text": "",
        "portfolio_name": "default",
        "model": "llama3",
        "method": "Auto (KI wählt)",
        "period": "1y",
        # Search
        "search_query": "",
        "search_results": [],
        "search_selected_idx": 0,
        # Easter Egg: Währungs-Klick-Counter
        "currency_clicks": 0,
        "currency_unlocked": False,
        "selected_currency": CURRENCIES[0],
        # Easter Egg: Zyklus-Tracking
        "prev_cycles": 0,
        "eggs_fired": set(),
        # Sidebar: Verlauf & letzte Vorhersage
        "history": [],
        "last_pred_ticker": "",
        "last_pred_signal": "",
        "last_pred_conf": 0.0,
        "last_pred_time": "",
        # Paper-Trading Parameter (Sidebar-Override)
        "pt_budget": DEFAULT_BUDGET_EUR,
        "pt_order_cost": ORDER_COST_EUR,
        "pt_spread": SPREAD_PERCENT,
        # Training-Zustand (für Animation/Sperre)
        "running_training": False,
        # Portfolio-Cache (vermeidet wiederholte yfinance-Calls)
        "pt_summary_cache": None,
        "pt_prices_cache": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()
_startup_check()

# ─────────────────────────────────────────────────────────────────────────────
# Chart-Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────
_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font=dict(color="#c9d1d9", family="IBM Plex Mono, monospace"),
    margin=dict(l=8, r=8, t=32, b=8),
)
_GREEN  = "#00ff88"
_RED    = "#ff4444"
_AMBER  = "#f0b429"
_BLUE   = "#58a6ff"
_PURPLE = "#bc8cff"


def _candlestick_pro(
    df: pd.DataFrame,
    ticker: str,
    show_volume: bool = True,
    show_sma: bool = True,
    show_ema: bool = False,
) -> go.Figure:
    rows = 2 if show_volume else 1
    row_heights = [0.75, 0.25] if show_volume else [1.0]
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.02,
    )
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color=_GREEN, decreasing_line_color=_RED,
        increasing_fillcolor=_GREEN, decreasing_fillcolor=_RED,
        name=ticker, showlegend=False,
    ), row=1, col=1)
    # SMAs
    if show_sma:
        for col_name, color, label in [
            ("SMA_20", _GREEN, "SMA 20"),
            ("SMA_50", _AMBER, "SMA 50"),
            ("SMA_200", _BLUE, "SMA 200"),
        ]:
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col_name],
                    mode="lines", name=label,
                    line=dict(color=color, width=1.2),
                ), row=1, col=1)
    # EMAs
    if show_ema:
        for col_name, color, label in [
            ("EMA_12", _PURPLE, "EMA 12"),
            ("EMA_26", "#ff9f43", "EMA 26"),
        ]:
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col_name],
                    mode="lines", name=label,
                    line=dict(color=color, width=1, dash="dot"),
                ), row=1, col=1)
    # Volume
    if show_volume and "Volume" in df.columns:
        colors = [_GREEN if c >= o else _RED
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=colors, name="Volumen",
            showlegend=False, opacity=0.7,
        ), row=2, col=1)
    fig.update_layout(
        **_DARK,
        height=460,
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10),
        ),
        xaxis2_showgrid=False if show_volume else None,
    )
    fig.update_xaxes(gridcolor="#1c2128", zeroline=False)
    fig.update_yaxes(gridcolor="#1c2128", zeroline=False)
    return fig


def _indicator_fig(df: pd.DataFrame, indicator: str) -> Optional[go.Figure]:
    fig = go.Figure()
    fig.update_layout(**_DARK, height=200)
    fig.update_xaxes(gridcolor="#1c2128")
    fig.update_yaxes(gridcolor="#1c2128")

    if indicator == "RSI" and "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI",
            line=dict(color=_BLUE, width=1.5), fill="tozeroy",
            fillcolor="rgba(88,166,255,0.06)",
        ))
        fig.add_hline(y=70, line_dash="dash", line_color=_RED,
                      annotation_text="Überkauft (70)", annotation_font_size=9)
        fig.add_hline(y=30, line_dash="dash", line_color=_GREEN,
                      annotation_text="Überverkauft (30)", annotation_font_size=9)
        fig.update_yaxes(range=[0, 100])
        fig.update_layout(title="RSI (14)")

    elif indicator == "MACD":
        if "MACD" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["MACD"], name="MACD",
                line=dict(color=_BLUE, width=1.5),
            ))
        if "MACD_Signal" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["MACD_Signal"], name="Signal",
                line=dict(color=_AMBER, width=1.2),
            ))
        if "MACD_Hist" in df.columns:
            hist = df["MACD_Hist"]
            colors = [_GREEN if v >= 0 else _RED for v in hist]
            fig.add_trace(go.Bar(
                x=df.index, y=hist, name="Histogramm",
                marker_color=colors, opacity=0.7,
            ))
        fig.add_hline(y=0, line_color="#30363d")
        fig.update_layout(title="MACD (12/26/9)")

    elif indicator == "Bollinger Bands":
        for col, color, name in [
            ("BB_Upper", _RED, "BB Oberes Band"),
            ("BB_Middle", _AMBER, "BB Mitte"),
            ("BB_Lower", _GREEN, "BB Unteres Band"),
        ]:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], name=name,
                    line=dict(color=color, width=1.2),
                ))
        if "Close" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"], name="Kurs",
                line=dict(color="#c9d1d9", width=1),
            ))
        fig.update_layout(title="Bollinger Bands (20, 2σ)")
    else:
        return None
    return fig


def _accuracy_gauge(accuracy: float) -> go.Figure:
    val = accuracy * 100
    color = _GREEN if val >= 55 else (_AMBER if val >= 45 else _RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={"suffix": "%", "font": {"size": 28, "color": color,
                                         "family": "IBM Plex Mono"}},
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#30363d",
                      tickfont=dict(size=9, color="#8b949e")),
            bar=dict(color=color, thickness=0.25),
            bgcolor="#161b22",
            borderwidth=1, bordercolor="#30363d",
            steps=[
                dict(range=[0, 40],  color="#2a0d0d"),
                dict(range=[40, 60], color="#1c2128"),
                dict(range=[60, 100],color="#0d2b1a"),
            ],
            threshold=dict(
                line=dict(color=_RED, width=3),
                thickness=0.75, value=50,
            ),
        ),
    ))
    fig.update_layout(**_DARK, height=220,
                      margin=dict(l=20, r=20, t=24, b=8))
    return fig


def _method_bars(method_scores: dict) -> go.Figure:
    if not method_scores:
        return go.Figure()
    items = sorted(method_scores.items(), key=lambda x: x[1], reverse=True)
    names = [i[0] for i in items]
    vals  = [i[1] for i in items]
    colors = [_GREEN if v >= 0.5 else _RED for v in vals]
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker_color=colors,
        text=[f"{v:.1%}" for v in vals],
        textposition="outside",
        textfont=dict(family="IBM Plex Mono", size=10),
    ))
    fig.add_vline(x=0.5, line_dash="dash", line_color="#30363d",
                  annotation_text="Zufall", annotation_font_size=9)
    fig.update_layout(
        **_DARK, height=max(200, len(names) * 36 + 60),
        xaxis=dict(range=[0, 1.05], tickformat=".0%", gridcolor="#1c2128"),
        yaxis=dict(gridcolor="#1c2128"),
        margin=dict(l=160, r=60, t=16, b=8),
    )
    return fig


def _equity_chart(
    perf_df: pd.DataFrame,
    start_budget: float,
    title: str = "Portfolio-Wert",
) -> go.Figure:
    fig = go.Figure()
    if perf_df.empty or "value" not in perf_df.columns:
        fig.update_layout(**_DARK, height=250)
        return fig
    x = perf_df.get("timestamp", perf_df.index)
    y = perf_df["value"]
    above = [v >= start_budget for v in y]
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines",
        name="Portfolio",
        line=dict(color=_GREEN, width=2),
        fill="tozeroy",
        fillcolor="rgba(0,255,136,0.06)",
    ))
    fig.add_hline(y=start_budget, line_dash="dash",
                  line_color="#30363d",
                  annotation_text=f"Start {start_budget:,.0f}€",
                  annotation_font_size=9)
    fig.update_layout(
        **_DARK, height=260,
        xaxis_title="", yaxis_title="Wert (€)",
        title=title,
    )
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="font-family:IBM Plex Mono,monospace;color:#00ff88;'
        f'font-size:20px;font-weight:700;letter-spacing:2px;">'
        f'{APP_ICON} {APP_TITLE}</div>'
        f'<div style="color:#8b949e;font-size:10px;margin-top:2px;">'
        f'v{APP_VERSION} · Lokale KI-Aktienanalyse</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Verlauf ──────────────────────────────────────────────────────────
    _section("📋 Zuletzt analysiert")
    if st.session_state.history:
        for hist_ticker in reversed(st.session_state.history[-5:]):
            if st.button(
                f"↗ {hist_ticker}", key=f"hist_{hist_ticker}",
                use_container_width=True,
            ):
                st.session_state.ticker = hist_ticker
                with st.spinner(f"Lade {hist_ticker}…"):
                    df_h = _ohlcv(hist_ticker, st.session_state.period)
                    if not df_h.empty:
                        st.session_state.df   = df_h
                        st.session_state.info = _info(hist_ticker)
                        st.session_state.prediction  = None
                        st.session_state.analysis_text = ""
                st.rerun()
    else:
        st.caption("Noch keine Aktien analysiert.")

    st.divider()

    # ── Letzte Vorhersage ─────────────────────────────────────────────────
    _section("🔮 Letzte KI-Vorhersage")
    if st.session_state.last_pred_signal:
        badge = _signal_badge_html(st.session_state.last_pred_signal)
        st.markdown(
            f'{badge} &nbsp; '
            f'<span style="color:#8b949e;font-size:11px;">'
            f'{st.session_state.last_pred_ticker} · '
            f'{st.session_state.last_pred_conf:.0%}</span>',
            unsafe_allow_html=True,
        )
        if st.session_state.last_pred_time:
            st.caption(st.session_state.last_pred_time)
    else:
        st.caption("Noch keine Vorhersage.")

    st.divider()

    # ── Easter Egg: Währungsauswahl ───────────────────────────────────────
    if ENABLE_EASTER_EGGS and st.session_state.currency_unlocked:
        _section("💱 Anzeigewährung")
        st.session_state.selected_currency = st.selectbox(
            "Währung",
            CURRENCIES,
            index=CURRENCIES.index(st.session_state.selected_currency),
            key="sidebar_currency_select",
            label_visibility="collapsed",
        )
        if st.button("🔒 Zurücksetzen", key="sb_currency_reset",
                     use_container_width=True):
            st.session_state.currency_clicks   = 0
            st.session_state.currency_unlocked = False
            st.session_state.selected_currency = CURRENCIES[0]
            st.rerun()

    # ── Paper-Trading Parameter ───────────────────────────────────────────
    st.divider()
    with st.expander("⚙️ Trading-Parameter"):
        st.session_state.pt_budget = st.number_input(
            "Startkapital (€)", value=float(st.session_state.pt_budget),
            step=1000.0, min_value=100.0, key="sb_budget",
        )
        st.session_state.pt_order_cost = st.number_input(
            "Ordergebühr (€)", value=float(st.session_state.pt_order_cost),
            step=0.5, min_value=0.0, key="sb_ordercost",
        )
        st.session_state.pt_spread = st.number_input(
            "Spread (%)", value=float(st.session_state.pt_spread),
            step=0.01, min_value=0.0, format="%.3f", key="sb_spread",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Haupt-Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📊 Analyse & Training",
    "💰 Paper Trading",
    "⚙️ Modell-Manager",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 – ANALYSE & TRAINING
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    # ── A: Suchleiste ────────────────────────────────────────────────────────
    _section("🔍 Aktiensuche  –  WKN, ISIN, Name oder Ticker")
    row_a, row_b, row_c, row_d = st.columns([4, 1, 1, 1])
    with row_a:
        q = st.text_input(
            "Suche", placeholder="z.B. BMW, 519000, Apple, SAP.DE",
            key="search_q", label_visibility="collapsed",
        )
    with row_b:
        do_search = st.button("🔍 Suchen", use_container_width=True, key="btn_search")
    with row_c:
        st.session_state.period = st.selectbox(
            "Zeitraum", ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=3, key="period_sel", label_visibility="collapsed",
        )
    with row_d:
        do_load = st.button("📥 Laden", use_container_width=True,
                             type="primary", key="btn_load")

    # Suche ausführen
    if do_search and q:
        with st.spinner("Suche läuft…"):
            results = _search(q)
        if results:
            st.session_state.search_results = results
            st.session_state.search_selected_idx = 0
        else:
            st.warning("Keine Ergebnisse gefunden.")

    # Autocomplete-Dropdown
    if st.session_state.search_results:
        opts = [
            f"{r.get('symbol','?')} – {r.get('name','')[:40]} ({r.get('exchange','')})"
            for r in st.session_state.search_results
        ]
        idx = st.selectbox(
            "Ergebnisse", range(len(opts)),
            format_func=lambda i: opts[i],
            key="search_sel",
            label_visibility="collapsed",
        )
        st.session_state.search_selected_idx = idx

    # Daten laden
    if do_load:
        # Ticker bestimmen: aus Suchergebnis oder direkt aus Text-Input
        if st.session_state.search_results and not (q and is_valid_ticker(q)):
            sel = st.session_state.search_results[
                st.session_state.search_selected_idx
            ]
            ticker_to_load = sel["symbol"]
        elif q:
            ticker_to_load = q.strip().upper()
        else:
            ticker_to_load = ""

        if ticker_to_load:
            # Cache für diesen Ticker invalidieren → garantiert frische Daten
            _ohlcv.clear()
            _info.clear()
            with st.spinner(f"Lade {ticker_to_load}…"):
                df_new = _ohlcv(ticker_to_load, st.session_state.period)
            if df_new.empty:
                st.error(df_new.attrs.get("error", "Fehler beim Laden der Daten."))
            else:
                st.session_state.ticker = ticker_to_load
                st.session_state.df     = df_new
                st.session_state.info   = _info(ticker_to_load)
                st.session_state.prediction   = None
                st.session_state.analysis_text = ""
                # Verlauf aktualisieren
                hist = st.session_state.history
                if ticker_to_load not in hist:
                    hist.append(ticker_to_load)
                if len(hist) > 10:
                    st.session_state.history = hist[-10:]
                st.toast(f"📊 {len(df_new)} Kerzen geladen", icon="✅")
                st.success(f"✅ {len(df_new)} Kerzen geladen.")
                st.rerun()
        else:
            st.toast("Bitte WKN, Ticker oder Firmenname eingeben.", icon="🚨")
            st.error("Bitte WKN, Ticker oder Firmenname eingeben.")

    # ── B: Chart + Controls ──────────────────────────────────────────────────
    if st.session_state.df is not None:
        df: pd.DataFrame = st.session_state.df
        ticker: str      = st.session_state.ticker
        info: dict       = st.session_state.info

        # Kopfzeile
        name  = info.get("name", ticker)
        curr  = info.get("currency", "")
        last  = float(df["Close"].iloc[-1])
        prev  = float(df["Close"].iloc[-2]) if len(df) > 1 else last
        chg   = (last - prev) / prev * 100 if prev else 0
        chg_c = _GREEN if chg >= 0 else _RED
        st.markdown(
            f'<div style="margin:8px 0 12px;">'
            f'<span style="font-family:IBM Plex Mono;font-size:22px;'
            f'font-weight:700;color:#c9d1d9;">{name}</span>&nbsp;&nbsp;'
            f'<span style="color:#8b949e;font-size:14px;">{ticker} · {curr}</span>'
            f'&nbsp;&nbsp;<span style="font-family:IBM Plex Mono;font-size:20px;'
            f'font-weight:700;color:#00ff88;">{last:.2f}</span>'
            f'&nbsp;<span style="color:{chg_c};font-size:14px;">{chg:+.2f}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1, 2])

        with col_left:
            _section("⚙️ Konfiguration")
            # Modell-Auswahl
            running_models = _models_list()
            model_opts = running_models if running_models else AVAILABLE_MODELS
            try:
                def_idx = model_opts.index(st.session_state.model)
            except ValueError:
                def_idx = 0
            st.session_state.model = st.selectbox(
                "🤖 KI-Modell", model_opts, index=def_idx, key="model_sel",
            )
            # Methode
            st.session_state.method = st.selectbox(
                "📐 Analyse-Methode", ANALYSIS_METHODS,
                index=ANALYSIS_METHODS.index(st.session_state.method)
                      if st.session_state.method in ANALYSIS_METHODS else 0,
                key="method_sel",
            )
            # Schnell-Aktionen
            st.divider()
            _section("⚡ Schnellaktionen")

            if st.button("🔮 Signal berechnen", use_container_width=True,
                         key="btn_quick_pred"):
                with st.spinner("Berechne Signal…"):
                    pred = predict(ticker, df, method=st.session_state.method,
                                  ml_bundle=load_model(ticker), training_state=load_state(ticker))
                    st.session_state.prediction   = pred
                    st.session_state.last_pred_ticker = ticker
                    st.session_state.last_pred_signal = pred.signal
                    st.session_state.last_pred_conf   = pred.confidence
                    st.session_state.last_pred_time   = time.strftime("%H:%M:%S")
                st.rerun()

            if st.session_state.prediction:
                pred = st.session_state.prediction
                st.markdown(
                    f'{_signal_badge_html(pred.signal)}'
                    f'&nbsp;<span style="color:#8b949e;font-size:12px;">'
                    f'{pred.confidence:.0%}</span>',
                    unsafe_allow_html=True,
                )
                if pred.summary:
                    st.caption(pred.summary[:120])

            # KI-Analyse
            if _check_ollama():
                if st.button("🤖 KI-Analyse starten", use_container_width=True,
                             key="btn_quick_ai"):
                    pred = st.session_state.prediction or predict(
                        ticker, df, method=st.session_state.method,
                        ml_bundle=load_model(ticker), training_state=load_state(ticker),
                    )
                    ctx = build_context_string(ticker, df, pred)
                    with st.spinner("KI analysiert…"):
                        try:
                            text = analyze_stock(
                                st.session_state.model, ticker, ctx,
                                method=st.session_state.method,
                            )
                            st.session_state.analysis_text = text
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("Ollama offline → Tab ⚙️")

            if st.session_state.analysis_text:
                st.divider()
                _section("📝 KI-Analyse")
                st.markdown(
                    _quote_html(st.session_state.analysis_text[:400] + "…"),
                    unsafe_allow_html=True,
                )

        with col_right:
            _section("📈 Candlestick-Chart")
            show_sma = st.checkbox("SMAs", value=True, key="chk_sma")
            show_vol = st.checkbox("Volumen", value=True, key="chk_vol")
            st.plotly_chart(
                _candlestick_pro(df, ticker, show_volume=show_vol, show_sma=show_sma),
            )
            ind_opts = ["– keiner –", "RSI", "MACD", "Bollinger Bands"]
            ind_sel  = st.selectbox("Indikator", ind_opts, key="ind_sel")
            if ind_sel != "– keiner –":
                fig_ind = _indicator_fig(df, ind_sel)
                if fig_ind:
                    st.plotly_chart(fig_ind)

    else:
        # Onboarding wenn noch keine Daten geladen
        st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        for col, icon, head, txt in [
            (c1, "📈", "Analysieren", "KI-gestützte Analyse mit lokalen LLMs. Keine Cloud, keine API-Keys."),
            (c2, "🎓", "Trainieren",  "Trainiere Vorhersagemodelle und verfolge deren Genauigkeit im Zeitverlauf."),
            (c3, "🏎️", "Paper-Trading", f"Starte mit {DEFAULT_BUDGET_EUR:,.0f}€ virtuellem Kapital und jage den Lambo."),
        ]:
            with col:
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;padding:24px;">'
                    f'<div style="font-size:40px;">{icon}</div>'
                    f'<div style="color:#00ff88;font-weight:700;margin:8px 0;">{head}</div>'
                    f'<div style="color:#8b949e;font-size:13px;">{txt}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── C: Training-Sektion ──────────────────────────────────────────────────
    if st.session_state.df is not None:
        st.divider()
        _section("🎓 Training & Backtesting")

        state   = load_state(st.session_state.ticker)
        trainer = StockTrainer()

        sub1, sub2, sub3 = st.tabs(["🤖 LLM-Zyklus", "🔄 Auto-Modus", "📊 Backtesting"])

        # ── LLM-Zyklus ──────────────────────────────────────────────────────
        with sub1:
            col_m, col_r = st.columns([1, 2])
            with col_m:
                t_method = st.selectbox(
                    "Methode",
                    [m for m in ANALYSIS_METHODS if m != "Auto (KI wählt)"],
                    key="train_method_llm",
                )
                btn_cycle = st.button("▶ Zyklus starten", use_container_width=True,
                                      type="primary", key="btn_llm_cycle")
            with col_r:
                if btn_cycle:
                    if not _check_ollama():
                        st.error("Ollama offline – bitte `ollama serve` starten.")
                    else:
                        anim_slot = st.empty()
                        quote = random.choice(_QUOTES)
                        anim_slot.markdown(
                            _ticker_html() + _quote_html(
                                f'<span class="sm-pulse">⬛</span> '
                                f'KI analysiert {st.session_state.ticker}… · {quote}'
                            ),
                            unsafe_allow_html=True,
                        )
                        st.session_state.running_training = True
                        with st.spinner(f"Trainingszyklus ({t_method})…"):
                            result = trainer.run_training_cycle(
                                st.session_state.ticker,
                                t_method,
                                st.session_state.model,
                            )
                        anim_slot.empty()
                        if result.get("error"):
                            st.error(result["error"])
                        else:
                            ok = result.get("correct", False)
                            pred_sig = result.get("prediction", "?")
                            actual   = result.get("actual", "?")
                            conf     = result.get("confidence", 0.0)
                            cycle    = result.get("cycle", 0)
                            m_acc    = result.get("method_accuracy", 0.0)
                            o_acc    = result.get("overall_accuracy", 0.0)

                            mc1, mc2, mc3, mc4 = st.columns(4)
                            mc1.metric("Vorhersage",
                                       pred_sig, "✅ Korrekt" if ok else "❌ Falsch")
                            mc2.metric("Konfidenz", f"{conf:.0%}")
                            mc3.metric("Methoden-Acc", f"{m_acc:.1%}")
                            mc4.metric("Gesamt-Acc", f"{o_acc:.1%}")

                            if result.get("reasoning"):
                                st.markdown(
                                    _quote_html(result["reasoning"][:300]),
                                    unsafe_allow_html=True,
                                )
                            # Easter Egg
                            if ENABLE_EASTER_EGGS:
                                egg = check_easter_egg({
                                    "cycles": cycle,
                                    "previous_cycles": st.session_state.prev_cycles,
                                    "accuracy": o_acc,
                                    "total_return_pct": None,
                                })
                                if egg:
                                    if CONFETTI_MARKER in egg:
                                        st.balloons()
                                        egg = egg.replace(CONFETTI_MARKER, "")
                                    st.info(egg)
                            st.session_state.prev_cycles = cycle

                            # Letzte Vorhersage in Sidebar aktualisieren
                            st.session_state.last_pred_ticker = st.session_state.ticker
                            st.session_state.last_pred_signal = pred_sig
                            st.session_state.last_pred_conf   = conf
                            st.session_state.last_pred_time   = time.strftime("%H:%M:%S")
                            st.rerun()
                else:
                    st.markdown(
                        _quote_html(random.choice(_QUOTES)),
                        unsafe_allow_html=True,
                    )

        # ── Auto-Modus ───────────────────────────────────────────────────────
        with sub2:
            col_x, col_y = st.columns([1, 2])
            with col_x:
                n_auto = st.slider("Zyklen", 1, 20, 3, key="auto_n")
                btn_auto = st.button("🔄 Auto starten", use_container_width=True,
                                     type="primary", key="btn_auto")
            with col_y:
                if btn_auto:
                    if not _check_ollama():
                        st.error("Ollama offline.")
                    else:
                        st.markdown(_ticker_html(), unsafe_allow_html=True)
                        last_res = None
                        with st.status(
                            f"Auto-Training: {n_auto} Zyklen für {st.session_state.ticker}",
                            expanded=True,
                        ) as status:
                            for i in range(n_auto):
                                status.update(
                                    label=f"Zyklus {i+1}/{n_auto} läuft…"
                                )
                                res = trainer.auto_mode(
                                    st.session_state.ticker,
                                    st.session_state.model,
                                )
                                last_res = res
                                if res.get("error"):
                                    st.write(f"❌ Zyklus {i+1}: {res['error']}")
                                    break
                                ok_sym = "✅" if res.get("correct") else "❌"
                                st.write(
                                    f"{ok_sym} Zyklus {i+1} · "
                                    f"**{res.get('prediction','?')}** · "
                                    f"Methode: {res.get('method','?')} · "
                                    f"Acc: {res.get('overall_accuracy', 0):.1%}"
                                )
                            status.update(label="Fertig!", state="complete")

                        if last_res and not last_res.get("error"):
                            if ENABLE_EASTER_EGGS:
                                egg = check_easter_egg({
                                    "cycles": last_res.get("cycle", 0),
                                    "previous_cycles": st.session_state.prev_cycles,
                                    "accuracy": last_res.get("overall_accuracy"),
                                    "total_return_pct": None,
                                })
                                if egg:
                                    if CONFETTI_MARKER in egg:
                                        st.balloons()
                                        egg = egg.replace(CONFETTI_MARKER, "")
                                    st.info(egg)
                            st.session_state.prev_cycles = last_res.get("cycle", 0)
                            st.rerun()

        # ── Backtesting ──────────────────────────────────────────────────────
        with sub3:
            bt_col1, bt_col2 = st.columns(2)
            with bt_col1:
                bt_method = st.selectbox(
                    "Methode",
                    [m for m in ANALYSIS_METHODS if m != "Auto (KI wählt)"],
                    key="bt_method",
                )
            with bt_col2:
                bt_budget = st.number_input(
                    "Startkapital (€)", value=DEFAULT_BUDGET_EUR,
                    step=1000.0, key="bt_budget",
                )
            if st.button("▶ Backtest starten", use_container_width=True,
                         key="btn_bt"):
                fn = SIGNAL_FUNCTIONS.get(bt_method)
                if not fn:
                    st.toast(f"Methode '{bt_method}' nicht verfügbar.", icon="🚨")
                    st.error(f"Methode '{bt_method}' nicht verfügbar.")
                else:
                    with st.spinner("Berechne Signale…"):
                        signals = {}
                        df_bt = st.session_state.df
                        for i in range(50, len(df_bt)):
                            try:
                                sig, _ = fn(df_bt.iloc[:i+1])
                                signals[df_bt.index[i]] = sig
                            except Exception:
                                signals[df_bt.index[i]] = "HALTEN"
                        sig_s  = pd.Series(signals)
                        result = backtest_signals(
                            st.session_state.ticker, df_bt, sig_s,
                            initial_cash=bt_budget,
                        )
                    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
                    bc1.metric("Rendite", f"{result.total_return_pct:+.2f}%")
                    bc2.metric("Buy & Hold", f"{result.buy_and_hold_pct:+.2f}%")
                    bc3.metric("Win-Rate", f"{result.win_rate:.0%}")
                    bc4.metric("Max Drawdown", f"{result.max_drawdown_pct:.2f}%")
                    bc5.metric("Sharpe", f"{result.sharpe_ratio:.2f}")
                    if result.equity_curve:
                        eq_df = pd.DataFrame({
                            "value": result.equity_curve,
                        })
                        st.plotly_chart(
                            _equity_chart(eq_df, bt_budget,
                                          f"Equity Curve – {bt_method}"),
                        )

        # ── Trainings-Statistiken ────────────────────────────────────────────
        state = load_state(st.session_state.ticker)
        if state.get("cycles", 0) > 0:
            st.divider()
            _section("📊 Trainings-Statistiken")

            s1, s2, s3 = st.columns([1, 1, 2])
            with s1:
                acc = state.get("current_accuracy") or state.get("accuracy") or 0.0
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;">'
                    f'<div class="sm-label">Trainingszyklen</div>'
                    f'<div class="sm-big-num">{state["cycles"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with s2:
                best = state.get("best_method") or "–"
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;">'
                    f'<div class="sm-label">Beste Methode</div>'
                    f'<div style="font-family:IBM Plex Mono;font-size:15px;'
                    f'font-weight:700;color:#f0b429;margin-top:8px;">{best}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with s3:
                if acc:
                    st.plotly_chart(
                        _accuracy_gauge(acc),
                    )

            if state.get("method_scores"):
                st.plotly_chart(
                    _method_bars(state["method_scores"]),
                )

            if state.get("insights"):
                _section("💡 KI-Erkenntnisse")
                for ins in reversed(state["insights"][-3:]):
                    st.markdown(_quote_html(ins), unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 – PAPER TRADING
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    pt = PaperTrader(
        name=st.session_state.portfolio_name,
        start_budget=st.session_state.pt_budget,
        order_cost=st.session_state.pt_order_cost,
        spread_pct=st.session_state.pt_spread,
    )
    pt_state = pt.load()

    # Aktuelle Preise für offene Positionen laden
    current_prices: dict[str, float] = {}
    for sym in pt_state.positions:
        d = _ohlcv(sym, "5d")
        current_prices[sym] = (
            float(d["Close"].iloc[-1]) if not d.empty
            else pt_state.positions[sym].get("avg_price", 0)
        )

    summary = pt.get_portfolio_summary(current_prices)

    # ── Portfolio KPIs ────────────────────────────────────────────────────────
    _section("💼 Portfolio-Übersicht")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    # Gesamtwert – klickbarer Button (Easter-Egg Klick-Counter)
    _currency     = st.session_state.selected_currency
    _display_val  = get_currency_display(summary["total_value"], _currency)
    _ret_color    = _GREEN if summary["total_return_pct"] >= 0 else _RED
    _ret_sign     = "+" if summary["total_return_pct"] >= 0 else ""
    with kpi1:
        if ENABLE_EASTER_EGGS:
            if st.button(
                f"💼 Gesamtwert\n{_display_val}",
                key="btn_total_click",
                help=(
                    f"Klick {st.session_state.currency_clicks + 1}"
                    f"/{CURRENCY_UNLOCK_CLICKS} bis zur Währungsauswahl 🤫"
                ),
                use_container_width=True,
            ):
                st.session_state.currency_clicks += 1
                if st.session_state.currency_clicks >= CURRENCY_UNLOCK_CLICKS:
                    st.session_state.currency_unlocked = True
                    st.rerun()
        else:
            st.metric("💼 Gesamtwert", _display_val)
        st.markdown(
            f'<span style="color:{_ret_color};font-family:IBM Plex Mono;">'
            f'{_ret_sign}{summary["total_return_pct"]:.2f}%</span>',
            unsafe_allow_html=True,
        )

    kpi2.metric("Cash",           f"{summary['cash']:,.2f} €")
    kpi3.metric("Positionen",     f"{summary['position_value']:,.2f} €")
    kpi4.metric(
        "Realisiert",
        f"{summary['realized_pnl']:+,.2f} €",
        delta_color="normal",
    )
    win_r = summary.get("win_rate", 0.0)
    n_sell = summary.get("num_sell_trades", 0)
    kpi5.metric("Win-Rate",       f"{win_r:.0%}" if n_sell else "–",
                f"{n_sell} Trades")

    # Währungsauswahl nach Unlock
    if ENABLE_EASTER_EGGS and st.session_state.currency_unlocked:
        st.markdown(
            '<div class="sm-card-accent">'
            '🎉 <strong>Easter Egg freigeschaltet!</strong> '
            'Die geheime Währungsauswahl ist jetzt in der Sidebar verfügbar.'
            '</div>',
            unsafe_allow_html=True,
        )

    # Trade-Count Easter Egg
    if ENABLE_EASTER_EGGS:
        trade_egg = get_trade_count_egg(summary.get("num_trades", 0))
        if trade_egg:
            egg_key = f"trade_egg_{summary.get('num_trades', 0)}"
            if egg_key not in st.session_state.eggs_fired:
                st.session_state.eggs_fired.add(egg_key)
                st.toast(trade_egg)

    # ── Lambo-O-Meter ─────────────────────────────────────────────────────────
    if ENABLE_EASTER_EGGS:
        st.divider()
        lv_pct, lv_msg = lambo_progress(summary["total_value"])
        _section(f"🏎️ Lambo-O-Meter  ·  {lambo_display(summary['total_value'])}")
        st.progress(min(lv_pct / 100, 1.0), text=lv_msg)

    # ── Performance-Chart ─────────────────────────────────────────────────────
    perf_df = pt.get_performance_chart()
    if len(perf_df) > 1:
        st.plotly_chart(
            _equity_chart(perf_df, float(pt_state.start_budget),
                          "Portfolio-Wert über Zeit"),
        )

    # ── Offene Positionen ─────────────────────────────────────────────────────
    st.divider()
    _section("📋 Offene Positionen")
    if summary.get("positions"):
        pos_df = pd.DataFrame(summary["positions"])
        st.dataframe(pos_df, use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="sm-card" style="text-align:center;color:#8b949e;'
            'padding:24px;">Keine offenen Positionen.</div>',
            unsafe_allow_html=True,
        )

    # ── Trading-Tabs ──────────────────────────────────────────────────────────
    st.divider()
    t_manual, t_auto, t_hist, t_reset = st.tabs([
        "🖱️ Manuelle Order", "🤖 Auto-Trade", "📋 Trade-Historie", "⚠️ Reset"
    ])

    with t_manual:
        if st.session_state.df is not None and st.session_state.ticker:
            ticker_pt = st.session_state.ticker
            df_pt     = st.session_state.df
            price_pt  = float(df_pt["Close"].iloc[-1])
            pt_state_now = pt.load()

            ma1, ma2, ma3, ma4 = st.columns(4)
            with ma1:
                pt_dir = st.selectbox("Richtung", ["BUY", "SELL"], key="pt_dir")
            with ma2:
                pt_frac = st.slider("Cash-Anteil", 0.05, 1.0, 0.2, 0.05,
                                    key="pt_frac")
            with ma3:
                st.metric("Kurs", f"{price_pt:.2f} €")
            with ma4:
                invest = pt_state_now.cash * pt_frac
                qty_est = invest / price_pt if price_pt > 0 else 0
                st.metric("Menge (ca.)", f"{qty_est:.4f}")

            pred_pt = st.session_state.prediction
            sig_str = pred_pt.signal if pred_pt else "MANUELL"

            if st.button(
                f"✅ {pt_dir} {ticker_pt}",
                use_container_width=True,
                type="primary",
                key="btn_pt_order",
            ):
                if pt_dir == "BUY":
                    spread_f = st.session_state.pt_spread / 100
                    qty = invest / (price_pt * (1 + spread_f))
                else:
                    qty = (pt_state_now.positions
                           .get(ticker_pt, {}).get("quantity", 0))
                res = pt.place_order(ticker_pt, pt_dir, qty, price_pt,
                                     signal=sig_str)
                if res["ok"]:
                    pnl_str = f"{res['pnl']:+.2f} €" if res.get("pnl") else "–"
                    st.success(
                        f"{pt_dir} {res['quantity']:.4f} × {ticker_pt} "
                        f"@ {res['exec_price']:.2f} € · PnL: {pnl_str}"
                    )
                    st.rerun()
                else:
                    st.error(res["error"])
        else:
            st.info("Bitte im Tab **📊 Analyse** zuerst eine Aktie laden.")

    with t_auto:
        st.markdown(
            "KI analysiert die gewählte Aktie und platziert automatisch "
            "Paper-Orders basierend auf LLM-Vorhersagen."
        )
        if st.session_state.ticker:
            aa1, aa2, aa3 = st.columns(3)
            with aa1:
                at_cycles = st.slider("Zyklen", 1, 10, 3, key="at_cycles")
            with aa2:
                at_invest = st.slider("Invest-Anteil/BUY",
                                      0.05, 0.5, 0.2, 0.05, key="at_invest")
            with aa3:
                at_method = st.selectbox(
                    "Methode", ANALYSIS_METHODS,
                    index=ANALYSIS_METHODS.index("Auto (KI wählt)"),
                    key="at_method",
                )
            if st.button("🚀 Auto-Trade starten", use_container_width=True,
                         type="primary", key="btn_auto_trade"):
                if not _check_ollama():
                    st.toast("Ollama offline.", icon="🚨")
                    st.error("Ollama offline.")
                else:
                    st.markdown(_ticker_html(), unsafe_allow_html=True)
                    with st.status(
                        f"Auto-Trade: {at_cycles} Zyklen",
                        expanded=True,
                    ) as at_status:
                        log = pt.auto_trade(
                            st.session_state.ticker,
                            st.session_state.model,
                            cycles=at_cycles,
                            method=at_method,
                            invest_pct=at_invest,
                        )
                        for entry in log:
                            action = entry.get("action", "?")
                            icon = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
                            st.write(
                                f"{icon} Zyklus {entry.get('cycle','?')}: "
                                f"**{action}** · {entry.get('prediction','?')} "
                                f"({entry.get('confidence', 0):.0%})"
                            )
                        at_status.update(label="Auto-Trade abgeschlossen!",
                                         state="complete")
                    st.rerun()
        else:
            st.info("Bitte zuerst eine Aktie laden.")

    with t_hist:
        if pt_state.trades:
            th = pd.DataFrame(pt_state.trades)
            cols = ["timestamp", "symbol", "direction", "quantity",
                    "exec_price", "pnl", "pnl_pct", "signal"]
            show = [c for c in cols if c in th.columns]
            st.dataframe(
                th[show].sort_values("timestamp", ascending=False),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Noch keine Trades.")

    with t_reset:
        st.warning("⚠️ Alle Positionen und Trade-Historie werden gelöscht!")
        reset_b = st.number_input(
            "Neues Startkapital (€)",
            value=float(pt_state.start_budget), step=1000.0,
            key="pt_reset_budget",
        )
        if st.button("🔄 Portfolio zurücksetzen", type="secondary",
                     key="btn_pt_reset"):
            pt.reset(new_budget=reset_b)
            st.success(f"Portfolio zurückgesetzt auf {reset_b:,.0f} €.")
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 – MODELL-MANAGER
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    _section("🔌 Ollama Status")

    ollama_st = _ollama_status()
    running   = ollama_st["running"]

    if running:
        model_count = ollama_st.get("model_count", 0)
        st.markdown(
            f'<div class="sm-card-accent">'
            f'<span class="sm-online">● ONLINE</span>'
            f'&nbsp;&nbsp;<span style="color:#8b949e;font-size:12px;">'
            f'{ollama_st.get("url","http://localhost:11434")} · '
            f'{model_count} Modell(e) installiert</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="sm-card" style="border-color:#ff4444;">'
            f'<span class="sm-offline">● OFFLINE</span>'
            f'&nbsp;&nbsp;<span style="color:#8b949e;font-size:12px;">'
            f'{ollama_st.get("error","Ollama nicht erreichbar.")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.expander("📖 Installationsanleitung"):
            st.markdown(ollama_st.get("install_guide", "Bitte Ollama unter https://ollama.ai installieren."))

    # ── Installierte Modelle ──────────────────────────────────────────────────
    st.divider()
    _section("📦 Installierte Modelle")

    if running:
        installed = _models_info()
        if installed:
            active_model = st.session_state.model
            for m in installed:
                name  = m.get("name", "?")
                size  = m.get("size_gb", 0)
                descr = m.get("description") or MODEL_DESCRIPTIONS.get(name, "")
                is_active = (name == active_model)
                badge = '<span class="sm-active-badge">AKTIV</span>' if is_active else ""
                st.markdown(
                    f'<div class="sm-model-row">'
                    f'<span style="font-family:IBM Plex Mono;font-weight:700;'
                    f'color:#c9d1d9;min-width:120px;">{name}</span>'
                    f'<span style="color:#8b949e;font-size:12px;min-width:70px;">'
                    f'{size:.1f} GB</span>'
                    f'<span style="color:#8b949e;font-size:12px;flex:1;">'
                    f'{descr}</span>'
                    f'{badge}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if st.button("🔄 Modell-Liste aktualisieren",
                         key="btn_refresh_models"):
                st.rerun()
        else:
            st.info("Ollama läuft, aber noch kein Modell installiert.")
    else:
        st.info("Ollama offline – keine Modelle verfügbar.")

    # ── Download ──────────────────────────────────────────────────────────────
    st.divider()
    _section("⬇️ Modell herunterladen")

    installed_names = set(_models_list()) if running else set()
    download_opts   = [m for m in AVAILABLE_MODELS if m not in installed_names]

    if not download_opts:
        st.success("✅ Alle empfohlenen Modelle sind bereits installiert.")
    else:
        dl_col1, dl_col2 = st.columns([2, 1])
        with dl_col1:
            dl_model = st.selectbox(
                "Modell wählen", download_opts, key="dl_model_sel",
            )
            descr = MODEL_DESCRIPTIONS.get(dl_model, "")
            if descr:
                st.caption(f"ℹ️ {descr}")
        with dl_col2:
            st.write("")
            btn_dl = st.button(
                f"⬇️ {dl_model} herunterladen",
                use_container_width=True,
                type="primary",
                key="btn_dl",
                disabled=not running,
            )

        if not running:
            st.warning("Ollama muss laufen um Modelle herunterzuladen.")

        if btn_dl and running:
            st.markdown(_ticker_html(), unsafe_allow_html=True)
            progress_slot = st.empty()
            bar_slot      = st.empty()
            done = False
            total_bytes = 0
            pulled_bytes = 0
            try:
                for i, line in enumerate(download_model(dl_model)):
                    if not line.strip():
                        continue
                    progress_slot.markdown(
                        f'<div class="sm-card" style="font-family:IBM Plex Mono;'
                        f'font-size:11px;color:#8b949e;">{line}</div>',
                        unsafe_allow_html=True,
                    )
                    # Einfacher Zähler als Fortschrittsindikator
                    pct = min((i % 200) / 200, 1.0)
                    bar_slot.progress(pct, text=f"Lade {dl_model}…")
                    done = True
            except Exception as e:
                st.toast(f"Download-Fehler: {e}", icon="🚨")
                st.error(f"Download-Fehler: {e}")

            progress_slot.empty()
            bar_slot.empty()
            if done:
                _models_list.clear()   # Modell-Cache invalidieren → sofortige Anzeige
                _models_info.clear()
                st.success(
                    f"✅ **{dl_model}** erfolgreich heruntergeladen! "
                    "Seite neu laden um das Modell zu nutzen."
                )
                st.rerun()

    # ── Modell-Vergleichstabelle ──────────────────────────────────────────────
    st.divider()
    _section("📊 Modell-Vergleich & Empfehlungen")

    comparison = [
        {
            "Modell":       "llama3",
            "Größe (ca.)":  "4.7 GB",
            "Stärken":      "Ausgewogene Analyse, gutes Deutsch/Englisch",
            "RAM":          "8 GB",
            "Empfohlen für":"Standardanalyse, Einsteiger",
            "⭐":            "⭐⭐⭐⭐⭐",
        },
        {
            "Modell":       "mistral",
            "Größe (ca.)":  "4.1 GB",
            "Stärken":      "Sehr schnell, effizient, gute Logik",
            "RAM":          "8 GB",
            "Empfohlen für":"Viele Auto-Zyklen, schnelles Training",
            "⭐":            "⭐⭐⭐⭐",
        },
        {
            "Modell":       "phi3",
            "Größe (ca.)":  "2.3 GB",
            "Stärken":      "Klein & sparsam, überraschend gut",
            "RAM":          "4 GB",
            "Empfohlen für":"Schwache Hardware, erste Tests",
            "⭐":            "⭐⭐⭐",
        },
        {
            "Modell":       "gemma2",
            "Größe (ca.)":  "5.4 GB",
            "Stärken":      "Googles Modell, strukturierte Ausgaben",
            "RAM":          "8 GB",
            "Empfohlen für":"JSON-Parsing, strukturierte Analysen",
            "⭐":            "⭐⭐⭐⭐",
        },
        {
            "Modell":       "qwen2",
            "Größe (ca.)":  "4.4 GB",
            "Stärken":      "Mehrsprachig, Mathematik-stärke",
            "RAM":          "8 GB",
            "Empfohlen für":"Internationale Aktien, Quantanalyse",
            "⭐":            "⭐⭐⭐⭐",
        },
    ]
    comp_df = pd.DataFrame(comparison)
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    # ── Aktive Konfiguration ──────────────────────────────────────────────────
    st.divider()
    _section("🔧 Aktive Konfiguration")
    st.markdown(
        '<div class="sm-card">'
        '<table style="width:100%;font-size:13px;color:#c9d1d9;">'
        f'<tr><td style="color:#8b949e;width:220px;">UCB1 Exploration-Konstante</td>'
        f'<td><code style="color:#00ff88;">{EXPLORATION_CONSTANT}</code>&nbsp;'
        f'<span style="color:#8b949e;font-size:11px;">(sqrt(2) = {math.sqrt(2):.4f})</span></td></tr>'
        f'<tr><td style="color:#8b949e;">Ollama Host</td>'
        f'<td><code>{os.getenv("OLLAMA_HOST", "http://localhost:11434")}</code></td></tr>'
        f'<tr><td style="color:#8b949e;">Cache TTL</td>'
        f'<td><code>{CACHE_TTL_HOURS} h</code></td></tr>'
        f'<tr><td style="color:#8b949e;">Log-Level</td>'
        f'<td><code>{os.getenv("LOG_LEVEL", "INFO")}</code></td></tr>'
        '</table>'
        '<div style="margin-top:8px;color:#8b949e;font-size:11px;">'
        'Werte aus <code>.env</code> änderbar – App neu starten zum Übernehmen.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # ── Über StockMind ────────────────────────────────────────────────────────
    st.divider()
    _section(f"ℹ️ Über {APP_TITLE} v{APP_VERSION}")
    st.markdown(
        f'<div class="sm-card">'
        f'<table style="width:100%;font-size:13px;color:#c9d1d9;">'
        f'<tr><td style="color:#8b949e;width:180px;">Dashboard</td><td>Streamlit</td></tr>'
        f'<tr><td style="color:#8b949e;">Marktdaten</td><td>yfinance (Yahoo Finance)</td></tr>'
        f'<tr><td style="color:#8b949e;">Lokale KI</td><td>Ollama (llama3, mistral, …)</td></tr>'
        f'<tr><td style="color:#8b949e;">ML-Modell</td><td>scikit-learn GradientBoosting</td></tr>'
        f'<tr><td style="color:#8b949e;">Charts</td><td>Plotly</td></tr>'
        f'<tr><td style="color:#8b949e;">Lambo-Ziel</td>'
        f'<td style="color:#00ff88;">Lamborghini Aventador SVJ = '
        f'{LAMBO_PRICE_EUR:,.0f} €</td></tr>'
        f'</table>'
        f'<div style="margin-top:12px;color:#8b949e;font-size:11px;">'
        f'⚠️ StockMind ist ein experimentelles Bildungs- und Unterhaltungstool. '
        f'Alle Analysen und Signale stellen keine Anlageberatung dar.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

