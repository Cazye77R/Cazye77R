"""Strategie-Labor: automatische Walk-Forward-Auswahl der besten Strategie."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from modules.strategies import STRATEGIES
from modules.strategy_selector import VERDICT_TEXT, SelectionResult, select_strategy

from ui.charts import GREEN, RED
from ui.state import cached_ohlcv


def _equity_fig(res: SelectionResult) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=res.oos_returns.index,
            y=(1 + res.oos_returns).cumprod(),
            name="Auto-Auswahl (out-of-sample)",
            line={"color": GREEN, "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=res.bh_returns.index,
            y=(1 + res.bh_returns).cumprod(),
            name="Buy & Hold",
            line={"color": RED, "width": 1.5, "dash": "dot"},
        )
    )
    fig.update_layout(
        height=340,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        template="plotly_dark",
        yaxis_title="Wert (Start = 1)",
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def _run(ticker: str, train_window: int, test_window: int, cost_bps: float) -> SelectionResult:
    df = cached_ohlcv(ticker, "10y")
    if df is None or df.empty:
        raise ValueError(
            df.attrs.get("error", "Keine Daten.") if df is not None else "Keine Daten."
        )
    return select_strategy(
        df, train_window=train_window, test_window=test_window, cost_bps=cost_bps
    )


def render(ticker: str) -> None:
    st.caption(
        f"Die KI testet {sum(len(s.param_sets()) for s in STRATEGIES.values())} "
        f"Strategie-Varianten aus {len(STRATEGIES)} Familien automatisch. In jedem Zeitfenster "
        "wählt sie die beste anhand der Vergangenheit und handelt sie danach ungesehen. "
        "Nur dieses Out-of-Sample-Ergebnis zählt."
    )
    c1, c2, c3 = st.columns(3)
    train_window = c1.select_slider("Auswahl-Fenster (Tage)", [252, 378, 504, 756], value=504)
    test_window = c2.select_slider("Test-Fenster (Tage)", [21, 42, 63, 126], value=63)
    cost_bps = c3.slider("Kosten je Wechsel (Basispunkte)", 0, 50, 10)

    if st.button("🧪 Beste Strategie finden", type="primary", key="btn_lab"):
        with st.spinner("Teste alle Strategien (10 Jahre Historie)…"):
            try:
                st.session_state["lab_result"] = {
                    "ticker": ticker,
                    "res": _run(ticker, train_window, test_window, float(cost_bps)),
                }
            except ValueError as exc:
                st.session_state["lab_result"] = None
                st.error(str(exc))

    stored = st.session_state.get("lab_result")
    if not stored:
        return
    if stored["ticker"] != ticker:
        st.info(f"Ergebnis stammt von {stored['ticker']} – für {ticker} neu starten.")
        return
    res: SelectionResult = stored["res"]
    m = res.metrics

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Auto (OOS) Rendite", f"{m['auto']['total_return_pct']:+.1f}%")
    k2.metric("Buy & Hold", f"{m['buy_hold']['total_return_pct']:+.1f}%")
    k3.metric(
        "Max. Drawdown",
        f"{m['auto']['max_drawdown_pct']:.1f}%",
        delta=f"B&H {m['buy_hold']['max_drawdown_pct']:.1f}%",
        delta_color="off",
    )
    k4.metric("Folds besser als B&H", f"{m['folds_beating_bh']}/{m['n_folds']}")

    {"besser": st.success, "schlechter": st.error, "unklar": st.info, "zu_wenig_daten": st.warning}[
        res.verdict
    ](f"{VERDICT_TEXT[res.verdict]} (t-Statistik der Überrendite: {m['excess_tstat']:+.2f})")

    if res.current:
        cur = res.current
        st.markdown(
            f"**Aktuelle Auswahl** (auf den letzten Tagen gewählt): {cur['strategy']} → "
            f"**{cur['position_now']}**"
        )
        st.caption("Keine Anlageberatung – ein Hinweis aus historischen Daten, keine Prognose.")

    st.plotly_chart(_equity_fig(res), width="stretch")

    st.markdown("**Strategie-Familien (Out-of-Sample, Parameter jeweils im Fenster gewählt)**")
    fam = pd.DataFrame(res.family_oos.values()).rename(
        columns={
            "label": "Strategie",
            "total_return_pct": "Rendite %",
            "sharpe": "Sharpe",
            "max_drawdown_pct": "Max DD %",
            "days": "Tage",
        }
    )
    st.dataframe(fam.sort_values("Sharpe", ascending=False), width="stretch", hide_index=True)

    with st.expander("Gewählte Strategie je Fenster"):
        st.dataframe(
            pd.DataFrame([f.__dict__ for f in res.folds]), width="stretch", hide_index=True
        )
