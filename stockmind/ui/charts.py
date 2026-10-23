from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────────────────────
# Chart-Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font=dict(color="#c9d1d9", family="IBM Plex Mono, monospace"),
    margin=dict(l=8, r=8, t=32, b=8),
)
GREEN = "#00ff88"
RED = "#ff4444"
AMBER = "#f0b429"
BLUE = "#58a6ff"
PURPLE = "#bc8cff"


def candlestick_pro(
    df: pd.DataFrame,
    ticker: str,
    show_volume: bool = True,
    show_sma: bool = True,
    show_ema: bool = False,
) -> go.Figure:
    rows = 2 if show_volume else 1
    row_heights = [0.75, 0.25] if show_volume else [1.0]
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.02,
    )
    # Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            increasing_line_color=GREEN,
            decreasing_line_color=RED,
            increasing_fillcolor=GREEN,
            decreasing_fillcolor=RED,
            name=ticker,
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    # SMAs
    if show_sma:
        for col_name, color, label in [
            ("SMA_20", GREEN, "SMA 20"),
            ("SMA_50", AMBER, "SMA 50"),
            ("SMA_200", BLUE, "SMA 200"),
        ]:
            if col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col_name],
                        mode="lines",
                        name=label,
                        line=dict(color=color, width=1.2),
                    ),
                    row=1,
                    col=1,
                )
    # EMAs
    if show_ema:
        for col_name, color, label in [
            ("EMA_12", PURPLE, "EMA 12"),
            ("EMA_26", "#ff9f43", "EMA 26"),
        ]:
            if col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col_name],
                        mode="lines",
                        name=label,
                        line=dict(color=color, width=1, dash="dot"),
                    ),
                    row=1,
                    col=1,
                )
    # Volume
    if show_volume and "Volume" in df.columns:
        colors = [GREEN if c >= o else RED for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                marker_color=colors,
                name="Volumen",
                showlegend=False,
                opacity=0.7,
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        **DARK,
        height=460,
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10),
        ),
        xaxis2_showgrid=False if show_volume else None,
    )
    fig.update_xaxes(gridcolor="#1c2128", zeroline=False)
    fig.update_yaxes(gridcolor="#1c2128", zeroline=False)
    return fig


def indicator_fig(df: pd.DataFrame, indicator: str) -> Optional[go.Figure]:
    fig = go.Figure()
    fig.update_layout(**DARK, height=200)
    fig.update_xaxes(gridcolor="#1c2128")
    fig.update_yaxes(gridcolor="#1c2128")

    if indicator == "RSI" and "RSI" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["RSI"],
                name="RSI",
                line=dict(color=BLUE, width=1.5),
                fill="tozeroy",
                fillcolor="rgba(88,166,255,0.06)",
            )
        )
        fig.add_hline(
            y=70,
            line_dash="dash",
            line_color=RED,
            annotation_text="Überkauft (70)",
            annotation_font_size=9,
        )
        fig.add_hline(
            y=30,
            line_dash="dash",
            line_color=GREEN,
            annotation_text="Überverkauft (30)",
            annotation_font_size=9,
        )
        fig.update_yaxes(range=[0, 100])
        fig.update_layout(title="RSI (14)")

    elif indicator == "MACD":
        if "MACD" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["MACD"],
                    name="MACD",
                    line=dict(color=BLUE, width=1.5),
                )
            )
        if "MACD_Signal" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["MACD_Signal"],
                    name="Signal",
                    line=dict(color=AMBER, width=1.2),
                )
            )
        if "MACD_Hist" in df.columns:
            hist = df["MACD_Hist"]
            colors = [GREEN if v >= 0 else RED for v in hist]
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=hist,
                    name="Histogramm",
                    marker_color=colors,
                    opacity=0.7,
                )
            )
        fig.add_hline(y=0, line_color="#30363d")
        fig.update_layout(title="MACD (12/26/9)")

    elif indicator == "Bollinger Bands":
        for col, color, name in [
            ("BB_Upper", RED, "BB Oberes Band"),
            ("BB_Middle", AMBER, "BB Mitte"),
            ("BB_Lower", GREEN, "BB Unteres Band"),
        ]:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col],
                        name=name,
                        line=dict(color=color, width=1.2),
                    )
                )
        if "Close" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Close"],
                    name="Kurs",
                    line=dict(color="#c9d1d9", width=1),
                )
            )
        fig.update_layout(title="Bollinger Bands (20, 2σ)")
    else:
        return None
    return fig


def accuracy_gauge(accuracy: float) -> go.Figure:
    val = accuracy * 100
    color = GREEN if val >= 55 else (AMBER if val >= 45 else RED)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=val,
            number={"suffix": "%", "font": {"size": 28, "color": color, "family": "IBM Plex Mono"}},
            gauge=dict(
                axis=dict(
                    range=[0, 100], tickcolor="#30363d", tickfont=dict(size=9, color="#8b949e")
                ),
                bar=dict(color=color, thickness=0.25),
                bgcolor="#161b22",
                borderwidth=1,
                bordercolor="#30363d",
                steps=[
                    dict(range=[0, 40], color="#2a0d0d"),
                    dict(range=[40, 60], color="#1c2128"),
                    dict(range=[60, 100], color="#0d2b1a"),
                ],
                threshold=dict(
                    line=dict(color=RED, width=3),
                    thickness=0.75,
                    value=50,
                ),
            ),
        )
    )
    fig.update_layout(**DARK, height=220, margin=dict(l=20, r=20, t=24, b=8))
    return fig


def method_bars(method_scores: dict) -> go.Figure:
    if not method_scores:
        return go.Figure()
    items = sorted(method_scores.items(), key=lambda x: x[1], reverse=True)
    names = [i[0] for i in items]
    vals = [i[1] for i in items]
    colors = [GREEN if v >= 0.5 else RED for v in vals]
    fig = go.Figure(
        go.Bar(
            x=vals,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1%}" for v in vals],
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=10),
        )
    )
    fig.add_vline(
        x=0.5,
        line_dash="dash",
        line_color="#30363d",
        annotation_text="Zufall",
        annotation_font_size=9,
    )
    fig.update_layout(
        **DARK,
        height=max(200, len(names) * 36 + 60),
        xaxis=dict(range=[0, 1.05], tickformat=".0%", gridcolor="#1c2128"),
        yaxis=dict(gridcolor="#1c2128"),
        margin=dict(l=160, r=60, t=16, b=8),
    )
    return fig


def equity_chart(
    perf_df: pd.DataFrame,
    start_budget: float,
    title: str = "Portfolio-Wert",
) -> go.Figure:
    fig = go.Figure()
    if perf_df.empty or "value" not in perf_df.columns:
        fig.update_layout(**DARK, height=250)
        return fig
    x = perf_df.get("timestamp", perf_df.index)
    y = perf_df["value"]
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="Portfolio",
            line=dict(color=GREEN, width=2),
            fill="tozeroy",
            fillcolor="rgba(0,255,136,0.06)",
        )
    )
    fig.add_hline(
        y=start_budget,
        line_dash="dash",
        line_color="#30363d",
        annotation_text=f"Start {start_budget:,.0f}€",
        annotation_font_size=9,
    )
    fig.update_layout(
        **DARK,
        height=260,
        xaxis_title="",
        yaxis_title="Wert (€)",
        title=title,
    )
    return fig


def underwater_chart(
    equity: pd.Series,
    title: str = "Drawdown",
) -> go.Figure:
    """Plotly-Chart: prozentualer Drawdown (Underwater-Kurve) über Zeit."""
    fig = go.Figure()
    if equity.empty:
        fig.update_layout(**DARK, height=180)
        return fig
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, float("nan")) * 100
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=dd.values,
            mode="lines",
            name="Drawdown",
            line=dict(color="#ff4444", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(255,68,68,0.12)",
        )
    )
    fig.add_hline(y=0, line_color="#30363d", line_width=1)
    fig.update_layout(
        **DARK,
        height=180,
        xaxis_title="",
        yaxis_title="Drawdown (%)",
        yaxis_tickformat=".1f",
        title=title,
        margin=dict(t=36, b=20),
    )
    return fig
