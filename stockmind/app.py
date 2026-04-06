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
    DEFAULT_BUDGET_EUR, DEFAULT_PERIOD, LAMBO_PRICE_EUR,
)
from modules.data_fetcher import fetch_ohlcv, fetch_info, is_valid_ticker
from modules.model_manager import (
    analyze_stock,
    get_available_models,
    get_available_models_with_info,
    get_ollama_status,
    list_local_models,                   # Compat für ui_components
)
from modules.trainer import train, load_state, list_trained_stocks
from modules.predictor import predict, build_context_string
from modules.backtester import (
    load_portfolio, save_portfolio, reset_portfolio,
    execute_trade, portfolio_summary, backtest_signals,
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

    df = st.session_state.df
    ticker = st.session_state.ticker
    state = load_state(ticker)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {ticker}")
        if state["cycles"] > 0:
            st.metric("Trainingszyklen", state["cycles"])
            st.metric("Letzte Genauigkeit", f"{state['accuracy']:.1%}" if state["accuracy"] else "–")
            st.caption(f"Zuletzt trainiert: {state['last_trained']}")
        else:
            st.info("Noch kein Modell trainiert.")

    with col2:
        horizon = st.slider("Vorhersage-Horizont (Tage)", 1, 20, 5)
        if st.button("🚀 Training starten", use_container_width=True):
            with st.spinner("Trainiere..."):
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

    # Feature Importance
    if state.get("feature_importance"):
        st.divider()
        st.markdown("### Feature Importance")
        fi = pd.Series(state["feature_importance"]).sort_values(ascending=True)
        fig = go.Figure(go.Bar(x=fi.values, y=fi.index, orientation="h",
                                marker_color="#2196f3"))
        fig.update_layout(template="plotly_dark", height=400, xaxis_title="Importance")
        st.plotly_chart(fig, use_container_width=True)

    # Trainings-Log
    if state.get("training_log"):
        st.divider()
        st.markdown("### Trainings-Historie")
        log_df = pd.DataFrame(state["training_log"])
        st.dataframe(log_df, use_container_width=True)

    # Alle trainierten Aktien
    st.divider()
    st.markdown("### Alle trainierten Aktien")
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

    portfolio_name = st.session_state.portfolio_name
    pf = load_portfolio(portfolio_name)

    # Aktuelle Preise für offene Positionen holen
    current_prices: dict[str, float] = {}
    for t in pf.positions:
        d = fetch_ohlcv(t, period="5d")
        if not d.empty:
            current_prices[t] = float(d["Close"].iloc[-1])
        else:
            current_prices[t] = pf.positions[t]["avg_price"]

    summary = portfolio_summary(pf, current_prices)

    # Easter Eggs prüfen
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

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gesamtwert", f"{summary['total_value']:,.2f} €",
                f"{summary['total_return_pct']:+.2f}%")
    col2.metric("Cash", f"{summary['cash']:,.2f} €")
    col3.metric("Positionswert", f"{summary['position_value']:,.2f} €")
    col4.metric("Trades gesamt", summary["num_trades"])

    # Lambo-Meter
    st.divider()
    lambo_widget(summary["total_value"])

    # Positionen
    st.divider()
    st.markdown("### Offene Positionen")
    if summary["positions"]:
        pos_df = pd.DataFrame(summary["positions"])
        st.dataframe(pos_df.set_index("ticker"), use_container_width=True)
    else:
        st.caption("Keine offenen Positionen.")

    # Order-Panel
    st.divider()
    st.markdown("### Order aufgeben")
    if st.session_state.df is not None and st.session_state.ticker:
        ticker = st.session_state.ticker
        df = st.session_state.df
        price = float(df["Close"].iloc[-1])

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            action = st.selectbox("Aktion", ["BUY", "SELL"])
        with col_b:
            fraction = st.slider("Cash-Anteil investieren", 0.05, 1.0, 0.1, 0.05)
        with col_c:
            st.metric("Aktueller Kurs", f"{price:.2f}")

        pred = st.session_state.prediction
        signal_str = pred.signal if pred else "MANUELL"

        if st.button(f"✅ Order ausführen: {action} {ticker}", use_container_width=True):
            ok, msg = execute_trade(pf, ticker, action, price, signal=signal_str, fraction=fraction)
            if ok:
                save_portfolio(pf, portfolio_name)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("Bitte links eine Aktie laden um Orders aufzugeben.")

    # Portfolio zurücksetzen
    st.divider()
    with st.expander("⚠️ Portfolio zurücksetzen"):
        new_budget = st.number_input("Neues Startkapital (€)", value=DEFAULT_BUDGET_EUR, step=1000.0)
        if st.button("🔄 Portfolio zurücksetzen", type="secondary"):
            reset_portfolio(portfolio_name, budget=new_budget)
            st.success(f"Portfolio zurückgesetzt auf {new_budget:,.0f} €.")
            st.rerun()

    # Trade-History
    st.divider()
    st.markdown("### Trade-Historie")
    if pf.trades:
        trades_df = pd.DataFrame([
            {
                "Datum": t.date[:10],
                "Ticker": t.ticker,
                "Aktion": t.action,
                "Stück": t.shares,
                "Kurs": t.price,
                "PnL": t.pnl,
                "Signal": t.signal,
            }
            for t in reversed(pf.trades)
        ])
        st.dataframe(trades_df, use_container_width=True)
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
