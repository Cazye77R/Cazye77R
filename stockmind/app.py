"""
StockMind – Streamlit Einstiegspunkt
Lokales KI-gestütztes Aktienanalyse-Tool
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    APP_TITLE, APP_ICON, APP_VERSION,
    ANALYSIS_METHODS, DEFAULT_BUDGET_EUR, DEFAULT_PERIOD,
    LAMBO_PRICE_EUR, ORDER_COST_EUR, SPREAD_PERCENT,
)
from modules.data_fetcher import fetch_ohlcv, fetch_info, is_valid_ticker
from modules.model_manager import (
    analyze_stock,
    get_available_models,
    get_available_models_with_info,
    get_ollama_status,
    list_local_models,                   # Compat für ui_components
)
from modules.trainer import train, load_state, list_trained_stocks, StockTrainer
from modules.predictor import predict, build_context_string
from modules.backtester import (
    PaperTrader,
    lambo_value, lambo_display, lambo_progress,
    backtest_signals,
    # Legacy-Compat (Paper-Trading-Seite Alt-Pfad)
    load_portfolio, save_portfolio, reset_portfolio,
    execute_trade, portfolio_summary,
)
from modules.easter_eggs import (
    check_triggers, random_motivation, format_lambo,
)
from modules.ui_components import (
    candlestick_chart, indicator_chart, signal_badge,
    lambo_widget, sidebar_model_selector, sidebar_analysis_method,
    sidebar_ticker_search, metrics_row, equity_curve_chart,
)


# ---------------------------------------------------------------------------
# Seiten-Konfiguration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session State initialisieren
# ---------------------------------------------------------------------------

def init_session() -> None:
    defaults = {
        "ticker": "",
        "df": None,
        "info": {},
        "prediction": None,
        "analysis_text": "",
        "portfolio_name": "default",
        "model": "llama3",
        "method": "Auto (KI wählt)",
        "page": "Dashboard",
        "prev_portfolio_value": 0.0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption(f"v{APP_VERSION} – Lokale KI-Aktienanalyse")
    st.divider()

    # Seitennavigation
    st.session_state.page = st.radio(
        "Navigation",
        ["Dashboard", "Training", "Paper-Trading", "Backtesting", "Einstellungen"],
        label_visibility="collapsed",
    )
    st.divider()

    # Ticker-Suche
    found_ticker = sidebar_ticker_search()
    if found_ticker:
        st.session_state.ticker = found_ticker

    # Manueller Ticker-Input als Fallback
    manual = st.text_input(
        "Oder Ticker direkt eingeben",
        value=st.session_state.ticker,
        placeholder="z.B. AAPL, SAP.DE",
    ).strip().upper()
    if manual:
        st.session_state.ticker = manual

    # Zeitraum
    period = st.selectbox(
        "Zeitraum",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        index=3,
    )

    # Daten laden
    if st.button("📥 Daten laden", use_container_width=True):
        if not st.session_state.ticker:
            st.error("Bitte einen Ticker eingeben.")
        elif not is_valid_ticker(st.session_state.ticker):
            st.error("Ungültiges Ticker-Format.")
        else:
            with st.spinner(f"Lade {st.session_state.ticker}..."):
                df_loaded = fetch_ohlcv(st.session_state.ticker, period=period)
                if df_loaded.empty:
                    st.error(df_loaded.attrs.get("error", "Unbekannter Fehler beim Laden."))
                else:
                    st.session_state.df = df_loaded
                    st.session_state.info = fetch_info(st.session_state.ticker)
                    st.session_state.prediction = None
                    st.session_state.analysis_text = ""
                    st.success(f"✅ {len(df_loaded)} Datenpunkte geladen.")

    st.divider()
    st.session_state.model = sidebar_model_selector()
    st.session_state.method = sidebar_analysis_method()
    st.divider()
    st.caption(random_motivation())


# ---------------------------------------------------------------------------
# Hauptbereich – Seiten
# ---------------------------------------------------------------------------

page = st.session_state.page

# ============================================================
# SEITE: DASHBOARD
# ============================================================
if page == "Dashboard":
    st.title(f"{APP_ICON} {APP_TITLE} – Dashboard")

    if st.session_state.df is None:
        st.info("👈 Bitte links einen Ticker eingeben und **Daten laden** klicken.")

        # Onboarding-Kacheln
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 📈 Analyse")
            st.write("KI-gestützte Aktienanalyse mit lokalen LLMs via Ollama.")
        with col2:
            st.markdown("### 🎓 Training")
            st.write("Trainiere Vorhersagemodelle je Aktie mit historischen Daten.")
        with col3:
            st.markdown("### 🏎️ Paper-Trading")
            st.write(f"Starte mit {DEFAULT_BUDGET_EUR:,.0f}€ virtuellem Kapital.\nZiel: 1 Lambo = {LAMBO_PRICE_EUR:,.0f}€")
        st.stop()

    df: pd.DataFrame = st.session_state.df
    info: dict = st.session_state.info
    ticker: str = st.session_state.ticker

    # Aktien-Kopfzeile
    name = info.get("name", ticker)
    currency = info.get("currency", "")
    st.markdown(f"## {name} `{ticker}` {currency}")

    col_a, col_b, col_c, col_d = st.columns(4)
    last = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    change = (last - prev) / prev * 100
    col_a.metric("Letzter Kurs", f"{last:.2f} {currency}", f"{change:+.2f}%")
    col_b.metric("52W-Hoch", f"{df['Close'].rolling(252).max().iloc[-1]:.2f}")
    col_c.metric("52W-Tief", f"{df['Close'].rolling(252).min().iloc[-1]:.2f}")
    col_d.metric("Ø Volumen (20T)", f"{df['Volume'].rolling(20).mean().iloc[-1]:,.0f}")

    st.divider()

    # Candlestick
    show_sma = st.checkbox("SMAs anzeigen", value=True)
    show_vol = st.checkbox("Volumen anzeigen", value=True)
    st.plotly_chart(
        candlestick_chart(df, ticker, show_sma=show_sma, show_volume=show_vol),
        use_container_width=True,
    )

    # Indikator-Auswahl
    ind_choice = st.selectbox("Indikator-Chart", ["– keiner –", "RSI", "MACD", "Bollinger Bands"])
    if ind_choice != "– keiner –":
        fig_ind = indicator_chart(df, ind_choice)
        if fig_ind:
            st.plotly_chart(fig_ind, use_container_width=True)

    st.divider()

    # Signal & KI-Analyse
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("### Signal")
        if st.button("🔮 Signal berechnen", use_container_width=True):
            pred = predict(ticker, df, method=st.session_state.method)
            st.session_state.prediction = pred
        if st.session_state.prediction:
            pred = st.session_state.prediction
            signal_badge(pred.signal, pred.confidence)
            st.caption(pred.summary)
            if pred.warnings:
                for w in pred.warnings:
                    st.warning(w)

    with col_right:
        st.markdown("### KI-Analyse")
        _ollama = get_ollama_status()
        ollama_ok = _ollama["running"] and _ollama["model_count"] > 0
        if not _ollama["running"]:
            st.warning(_ollama["error"])
            with st.expander("Installationsanleitung"):
                st.markdown(_ollama["install_guide"])
        elif not ollama_ok:
            st.warning("Ollama läuft, aber kein Modell installiert. Sidebar → Modell herunterladen.")
        else:
            if st.button(
                f"🤖 Analysieren mit {st.session_state.model}",
                use_container_width=True,
                disabled=not ollama_ok,
            ):
                pred = st.session_state.prediction or predict(ticker, df, method=st.session_state.method)
                st.session_state.prediction = pred
                ctx = build_context_string(ticker, df, pred)
                with st.spinner("KI analysiert..."):
                    try:
                        text = analyze_stock(
                            st.session_state.model, ticker, ctx,
                            method=st.session_state.method,
                        )
                        st.session_state.analysis_text = text
                    except ConnectionError as e:
                        st.error(str(e))

            if st.session_state.analysis_text:
                st.markdown(st.session_state.analysis_text)

    # Einzelsignale
    if st.session_state.prediction and st.session_state.prediction.indicator_signals:
        st.divider()
        st.markdown("### Indikatoren-Signale")
        sig_df = pd.DataFrame(st.session_state.prediction.indicator_signals).T
        st.dataframe(sig_df, use_container_width=True)

    # Rohdaten
    with st.expander("📋 Rohdaten anzeigen"):
        st.dataframe(df.tail(50), use_container_width=True)


# ============================================================
# SEITE: TRAINING
# ============================================================
elif page == "Training":
    st.title("🎓 Training")

    if st.session_state.df is None:
        st.info("Bitte erst links eine Aktie laden.")
        st.stop()

    df     = st.session_state.df
    ticker = st.session_state.ticker
    state  = load_state(ticker)
    trainer = StockTrainer()

    # ── Übersichts-KPIs ──────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Trainingszyklen", state["cycles"])
    acc = state.get("current_accuracy") or state.get("accuracy")
    col2.metric("Gesamtgenauigkeit", f"{acc:.1%}" if acc else "–")
    best = state.get("best_method") or "–"
    best_score = state.get("method_scores", {}).get(best)
    col3.metric(
        "Beste Methode",
        best,
        f"{best_score:.1%}" if best_score else None,
    )
    if state.get("last_trained"):
        st.caption(f"Zuletzt trainiert: {state['last_trained'][:19]} mit Modell: {state.get('model_used', '–')}")

    st.divider()

    # ── Trainings-Modi ────────────────────────────────────────
    tab_llm, tab_auto, tab_sklearn = st.tabs(
        ["🤖 LLM-Zyklus", "🔄 Auto-Modus", "📐 sklearn/GBM"]
    )

    with tab_llm:
        st.markdown("**Einzelner LLM-Trainingszyklus** – wähle Methode und starte.")
        t_method = st.selectbox(
            "Analyse-Methode",
            [m for m in ANALYSIS_METHODS if m != "Auto (KI wählt)"],
            key="train_method",
        )
        if st.button("▶️ Zyklus starten", use_container_width=True, key="btn_llm"):
            if not get_ollama_status()["running"]:
                st.error("Ollama nicht erreichbar. Bitte `ollama serve` starten.")
            else:
                with st.spinner(f"Trainingszyklus läuft ({t_method})…"):
                    result = trainer.run_training_cycle(
                        ticker, t_method, st.session_state.model
                    )
                if result.get("error"):
                    st.error(result["error"])
                else:
                    tick = "✅" if result["correct"] else "❌"
                    st.success(
                        f"{tick} Zyklus {result['cycle']} | "
                        f"Vorhersage: **{result['prediction']}** "
                        f"(Konfidenz {result['confidence']:.0%}) | "
                        f"Tatsächlich: **{result['actual']}** | "
                        f"Methoden-Acc: {result['method_accuracy']:.1%}"
                    )
                    st.markdown(f"**Begründung:** {result['reasoning']}")
                    st.rerun()

    with tab_auto:
        st.markdown(
            "**Auto-Modus** – testet alle Methoden reihum (UCB1-Auswahl), "
            "priorisiert Methoden mit höchster bisheriger Genauigkeit."
        )
        n_auto = st.slider("Anzahl Zyklen", 1, 10, 3, key="auto_cycles")
        if st.button("🔄 Auto-Training starten", use_container_width=True, key="btn_auto"):
            if not get_ollama_status()["running"]:
                st.error("Ollama nicht erreichbar.")
            else:
                prog = st.progress(0, text="Starte…")
                last_result = None
                for i in range(n_auto):
                    prog.progress((i + 1) / n_auto, text=f"Zyklus {i+1}/{n_auto}…")
                    last_result = trainer.auto_mode(ticker, st.session_state.model)
                    if last_result.get("error"):
                        st.error(last_result["error"])
                        break
                prog.empty()
                if last_result and not last_result.get("error"):
                    st.success(
                        f"✅ {n_auto} Zyklen abgeschlossen | "
                        f"Bevorzugte Methode: **{last_result.get('preferred_method', '–')}**"
                    )
                    st.rerun()

    with tab_sklearn:
        st.markdown(
            "**sklearn GradientBoosting** – klassisches ML auf technischen Features "
            "(kein LLM nötig, schneller)."
        )
        horizon = st.slider("Vorhersage-Horizont (Tage)", 1, 20, 5, key="sklearn_horizon")
        if st.button("🚀 sklearn Training", use_container_width=True, key="btn_sklearn"):
            with st.spinner("Trainiere GradientBoosting…"):
                try:
                    new_state = train(ticker, df, horizon=horizon)
                    st.success(
                        f"✅ Training abgeschlossen! "
                        f"Zyklus {new_state['cycles']} | "
                        f"Genauigkeit: {new_state['accuracy']:.1%}"
                    )
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ── Method Scores ─────────────────────────────────────────
    if state.get("method_scores"):
        st.divider()
        st.markdown("### Methoden-Vergleich")
        ms = state["method_scores"]
        ms_df = pd.DataFrame(
            [{"Methode": k, "Genauigkeit": v, "Balken": v} for k, v in sorted(
                ms.items(), key=lambda x: x[1], reverse=True
            )]
        )
        fig_ms = go.Figure(go.Bar(
            x=list(ms.values()),
            y=list(ms.keys()),
            orientation="h",
            marker_color=["#26a69a" if v >= 0.5 else "#ef5350" for v in ms.values()],
            text=[f"{v:.1%}" for v in ms.values()],
            textposition="outside",
        ))
        fig_ms.add_vline(x=0.5, line_dash="dash", line_color="#9e9e9e",
                         annotation_text="Zufall (50%)")
        fig_ms.update_layout(
            template="plotly_dark", height=300,
            xaxis=dict(range=[0, 1], tickformat=".0%"),
            margin=dict(l=160),
        )
        st.plotly_chart(fig_ms, use_container_width=True)

    # ── Accuracy-Verlauf ──────────────────────────────────────
    if state.get("accuracy_history"):
        st.divider()
        st.markdown("### Accuracy-Verlauf")
        ah = pd.DataFrame(state["accuracy_history"])
        if "accuracy_snapshot" in ah.columns:
            fig_acc = go.Figure(go.Scatter(
                x=ah.index + 1,
                y=ah["accuracy_snapshot"],
                mode="lines+markers",
                name="Gesamt-Accuracy",
                line=dict(color="#2196f3"),
            ))
            fig_acc.add_hline(y=0.5, line_dash="dash", line_color="#9e9e9e",
                              annotation_text="Zufallsniveau")
            fig_acc.update_layout(
                template="plotly_dark", height=280,
                xaxis_title="Zyklus", yaxis=dict(tickformat=".0%", range=[0, 1]),
            )
            st.plotly_chart(fig_acc, use_container_width=True)
        with st.expander("Accuracy-Tabelle"):
            st.dataframe(ah, use_container_width=True)

    # ── Insights ─────────────────────────────────────────────
    if state.get("insights"):
        st.divider()
        st.markdown("### KI-Erkenntnisse (letzte Zyklen)")
        for ins in reversed(state["insights"]):
            st.caption(ins)

    # ── Feature Importance (sklearn) ──────────────────────────
    if state.get("feature_importance"):
        st.divider()
        st.markdown("### Feature Importance (sklearn/GBM)")
        fi = pd.Series(state["feature_importance"]).sort_values(ascending=True)
        fig = go.Figure(go.Bar(
            x=fi.values, y=fi.index, orientation="h", marker_color="#ff9800"
        ))
        fig.update_layout(template="plotly_dark", height=400, xaxis_title="Importance")
        st.plotly_chart(fig, use_container_width=True)

    # ── Alle trainierten Aktien ───────────────────────────────
    st.divider()
    st.markdown("### Alle trainierten Symbole")
    trained = list_trained_stocks()
    if trained:
        st.write(", ".join(trained))
    else:
        st.caption("Noch keine Modelle trainiert.")


# ============================================================
# SEITE: PAPER-TRADING
# ============================================================
elif page == "Paper-Trading":
    st.title("💼 Paper-Trading")

    # ── Konfiguration ──────────────────────────────────────
    with st.sidebar.expander("⚙️ Trading-Parameter"):
        pt_budget    = st.number_input("Startkapital (€)",  value=DEFAULT_BUDGET_EUR, step=1000.0, key="pt_budget")
        pt_ordercost = st.number_input("Ordergebühr (€)",   value=ORDER_COST_EUR,     step=0.5,    key="pt_ordercost")
        pt_spread    = st.number_input("Spread (%)",         value=SPREAD_PERCENT,     step=0.05,   key="pt_spread",
                                       format="%.3f")

    portfolio_name = st.session_state.portfolio_name
    pt = PaperTrader(
        name=portfolio_name,
        start_budget=pt_budget,
        order_cost=pt_ordercost,
        spread_pct=pt_spread,
    )

    # Aktuelle Preise für offene Positionen
    pt_state = pt.load()
    current_prices: dict[str, float] = {}
    for sym in pt_state.positions:
        d = fetch_ohlcv(sym, period="5d")
        current_prices[sym] = float(d["Close"].iloc[-1]) if not d.empty else pt_state.positions[sym]["avg_price"]

    summary = pt.get_portfolio_summary(current_prices)

    # Easter Eggs
    eggs = check_triggers(
        summary["total_value"],
        summary["total_return_pct"],
        summary["num_trades"],
        summary["positions"],
        st.session_state.prev_portfolio_value,
    )
    st.session_state.prev_portfolio_value = summary["total_value"]
    for egg in eggs:
        st.toast(f"{egg.emoji} {egg.title}", icon=egg.emoji)
        st.info(f"**{egg.title}**\n\n{egg.message}")

    # ── KPIs ──────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Gesamtwert",    f"{summary['total_value']:,.2f} €",
                f"{summary['total_return_pct']:+.2f}%")
    col2.metric("Cash",          f"{summary['cash']:,.2f} €")
    col3.metric("Positionswert", f"{summary['position_value']:,.2f} €")
    col4.metric("Realisierter G/V", f"{summary['realized_pnl']:+,.2f} €")
    col5.metric("Win-Rate",      f"{summary['win_rate']:.0%}" if summary["num_sell_trades"] else "–",
                f"{summary['num_sell_trades']} Trades")

    # ── Lambo-Meter ───────────────────────────────────────
    st.divider()
    lv_pct, lv_msg = lambo_progress(summary["total_value"])
    st.markdown(f"### 🏎️ Lambo-O-Meter  ·  {lambo_display(summary['total_value'])}")
    st.progress(lv_pct / 100, text=lv_msg)

    # ── Performance-Chart ─────────────────────────────────
    perf_df = pt.get_performance_chart()
    if len(perf_df) > 1:
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(
            x=perf_df["timestamp"], y=perf_df["value"],
            mode="lines", name="Portfolio", line=dict(color="#2196f3", width=2),
            fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
        ))
        fig_perf.add_hline(y=pt_state.start_budget, line_dash="dash",
                           line_color="#9e9e9e", annotation_text="Start")
        fig_perf.update_layout(template="plotly_dark", height=280,
                               xaxis_title="Zeit", yaxis_title="Wert (€)")
        st.plotly_chart(fig_perf, use_container_width=True)

    # ── Positionen ────────────────────────────────────────
    st.divider()
    st.markdown("### Offene Positionen")
    if summary["positions"]:
        st.dataframe(pd.DataFrame(summary["positions"]), use_container_width=True, hide_index=True)
    else:
        st.caption("Keine offenen Positionen.")

    # ── Tabs: Manuell | Auto-Trade ────────────────────────
    st.divider()
    tab_manual, tab_auto = st.tabs(["🖱️ Manuelle Order", "🤖 Auto-Trade (KI)"])

    with tab_manual:
        if st.session_state.df is not None and st.session_state.ticker:
            ticker_pt = st.session_state.ticker
            df_pt     = st.session_state.df
            price_pt  = float(df_pt["Close"].iloc[-1])

            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                pt_dir = st.selectbox("Richtung", ["BUY", "SELL"], key="pt_dir")
            with col_b:
                pt_frac = st.slider("Cash-Anteil", 0.05, 1.0, 0.2, 0.05, key="pt_frac")
            with col_c:
                st.metric("Aktueller Kurs", f"{price_pt:.2f}")
            with col_d:
                invest_eur = pt_state.cash * pt_frac
                qty_est    = invest_eur / price_pt if price_pt > 0 else 0
                st.metric("Geschätzte Menge", f"{qty_est:.4f}")

            pred_pt    = st.session_state.prediction
            sig_str    = pred_pt.signal if pred_pt else "MANUELL"

            if st.button(f"✅ {pt_dir} {ticker_pt}", use_container_width=True, key="btn_pt_order"):
                qty = (pt_state.cash * pt_frac) / (price_pt * (1 + pt_spread/100)) if pt_dir == "BUY" else \
                      (pt_state.positions.get(ticker_pt, {}).get("quantity", 0))
                res = pt.place_order(ticker_pt, pt_dir, qty, price_pt, signal=sig_str)
                if res["ok"]:
                    st.success(
                        f"{pt_dir} {res['quantity']:.4f} × {ticker_pt} @ {res['exec_price']:.2f} € "
                        f"| PnL: {res['pnl']:+.2f} €"
                    )
                    st.rerun()
                else:
                    st.error(res["error"])
        else:
            st.info("Bitte links eine Aktie laden.")

    with tab_auto:
        st.markdown(
            "**Auto-Trade**: KI analysiert die Aktie und platziert automatisch "
            "Paper-Orders basierend auf Vorhersagen."
        )
        if st.session_state.ticker:
            col_x, col_y, col_z = st.columns(3)
            with col_x:
                at_cycles = st.slider("Anzahl Zyklen", 1, 10, 3, key="at_cycles")
            with col_y:
                at_invest = st.slider("Invest-Anteil je BUY", 0.05, 0.5, 0.2, 0.05, key="at_invest")
            with col_z:
                at_method = st.selectbox("Methode", ANALYSIS_METHODS, key="at_method",
                                         index=ANALYSIS_METHODS.index("Auto (KI wählt)"))

            if st.button("🚀 Auto-Trade starten", use_container_width=True, key="btn_auto_trade"):
                if not get_ollama_status()["running"]:
                    st.error("Ollama nicht erreichbar.")
                else:
                    with st.spinner(f"Führe {at_cycles} Auto-Trade-Zyklen aus…"):
                        log = pt.auto_trade(
                            st.session_state.ticker,
                            st.session_state.model,
                            cycles=at_cycles,
                            method=at_method,
                            invest_pct=at_invest,
                        )
                    st.success(f"✅ {len(log)} Zyklen abgeschlossen")
                    st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)
                    st.rerun()
        else:
            st.info("Bitte links eine Aktie laden.")

    # ── Reset ─────────────────────────────────────────────
    st.divider()
    with st.expander("⚠️ Portfolio zurücksetzen"):
        reset_budget = st.number_input("Neues Startkapital (€)", value=float(pt_state.start_budget), step=1000.0)
        if st.button("🔄 Zurücksetzen", type="secondary"):
            pt.reset(new_budget=reset_budget)
            st.success(f"Portfolio zurückgesetzt auf {reset_budget:,.0f} €.")
            st.rerun()

    # ── Trade-Historie ────────────────────────────────────
    st.divider()
    st.markdown("### Trade-Historie")
    if pt_state.trades:
        th_df = pd.DataFrame(pt_state.trades)
        cols  = ["timestamp","symbol","direction","quantity","exec_price","pnl","pnl_pct","method","signal"]
        show_cols = [c for c in cols if c in th_df.columns]
        st.dataframe(th_df[show_cols].sort_values("timestamp", ascending=False),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("Noch keine Trades.")


# ============================================================
# SEITE: BACKTESTING
# ============================================================
elif page == "Backtesting":
    st.title("📊 Backtesting")

    if st.session_state.df is None:
        st.info("Bitte erst links eine Aktie laden.")
        st.stop()

    df = st.session_state.df
    ticker = st.session_state.ticker

    st.markdown(f"Backtesting für **{ticker}** mit {len(df)} Datenpunkten.")

    col1, col2 = st.columns(2)
    with col1:
        bt_method = st.selectbox(
            "Methode",
            ["SMA Crossover", "RSI", "MACD", "Bollinger Bands"],
        )
    with col2:
        bt_budget = st.number_input("Startkapital (€)", value=DEFAULT_BUDGET_EUR, step=1000.0)

    if st.button("▶️ Backtest starten", use_container_width=True):
        from modules.predictor import SIGNAL_FUNCTIONS

        with st.spinner("Berechne Signale..."):
            fn = SIGNAL_FUNCTIONS.get(bt_method)
            if not fn:
                st.error(f"Methode '{bt_method}' nicht verfügbar.")
                st.stop()

            # Signale je Datum berechnen
            signals = {}
            for i in range(50, len(df)):
                slice_df = df.iloc[:i+1]
                try:
                    sig, _ = fn(slice_df)
                    signals[df.index[i]] = sig
                except Exception:
                    signals[df.index[i]] = "HALTEN"

            signal_series = pd.Series(signals)
            result = backtest_signals(ticker, df, signal_series, initial_cash=bt_budget)

        # Ergebnisse
        st.divider()
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Strategie-Rendite", f"{result.total_return_pct:+.2f}%")
        col_b.metric("Buy & Hold", f"{result.buy_and_hold_pct:+.2f}%")
        col_c.metric("Win-Rate", f"{result.win_rate:.0%}")
        col_d.metric("Max. Drawdown", f"{result.max_drawdown_pct:.2f}%")

        st.metric("Sharpe Ratio", f"{result.sharpe_ratio:.3f}")
        st.metric("Anzahl Trades", result.num_trades)

        # Equity Curve
        st.plotly_chart(
            equity_curve_chart(result.equity_curve, bt_budget, f"Equity Curve – {bt_method}"),
            use_container_width=True,
        )

        # Trade-Details
        if result.trades:
            with st.expander("Trade-Details"):
                st.dataframe(pd.DataFrame(result.trades), use_container_width=True)


# ============================================================
# SEITE: EINSTELLUNGEN
# ============================================================
elif page == "Einstellungen":
    st.title("⚙️ Einstellungen")

    st.markdown("### Ollama Status")
    _status = get_ollama_status()
    if _status["running"]:
        models_detail = get_available_models_with_info() if _status["model_count"] else []
        st.success(f"✅ Ollama erreichbar unter {_status['url']} | {_status['model_count']} Modell(e) installiert")
        if models_detail:
            st.dataframe(
                pd.DataFrame(models_detail)[["name", "size_gb", "modified", "description"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Noch kein Modell installiert. Sidebar → Modell auswählen → herunterladen.")
    else:
        st.error(f"❌ {_status['error']}")
        st.markdown(_status["install_guide"])

    st.divider()
    st.markdown("### Über StockMind")
    st.markdown(f"""
    **{APP_TITLE}** v{APP_VERSION}

    Ein lokales, KI-gestütztes Aktienanalyse-Tool das vollständig auf deinem Rechner läuft.

    | Komponente | Technologie |
    |---|---|
    | Dashboard | Streamlit |
    | Marktdaten | yfinance |
    | Lokale KI | Ollama |
    | ML-Modell | scikit-learn (GradientBoosting) |
    | Charts | Plotly |

    > ⚠️ **Haftungsausschluss:** StockMind ist ein experimentelles Tool zur Bildung und
    > Unterhaltung. Alle Analysen und Signale stellen **keine Anlageberatung** dar.
    > Investitionsentscheidungen liegen ausschließlich in deiner Verantwortung.
    """)

    st.divider()
    st.markdown("### 🏎️ Lambo-Kurs")
    st.info(f"1 Lambo (Aventador SVJ) = **{LAMBO_PRICE_EUR:,.0f} €**")
    test_val = st.number_input("Portfolio-Wert testen (€)", value=10_000.0, step=1_000.0)
    st.markdown(f"Das entspricht: {format_lambo(test_val)}")
