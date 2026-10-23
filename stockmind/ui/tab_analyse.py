from __future__ import annotations

import html
import random
import time

import pandas as pd
import streamlit as st
from config import (
    ANALYSIS_METHODS,
    AVAILABLE_MODELS,
    DEFAULT_BUDGET_EUR,
    ENABLE_EASTER_EGGS,
)
from modules.backtester import (
    backtest_signals,
    compute_metrics,
)
from modules.data_fetcher import (
    get_data_quality_report,
    invalidate_cache,
)
from modules.easter_eggs import (
    CONFETTI_MARKER,
    check_easter_egg,
)
from modules.explainer import explain_decision
from modules.predictor import SIGNAL_FUNCTIONS, predict
from modules.sentiment_analyzer import analyze_news
from modules.trainer import (
    _BANDIT_NAMES,
    StockTrainer,
    load_model,
    load_state,
)
from modules.trainer import (
    train as train_ml_model,
)

from ui.charts import (
    GREEN,
    RED,
    accuracy_gauge,
    candlestick_pro,
    equity_chart,
    indicator_fig,
    method_bars,
    underwater_chart,
)
from ui.state import (
    cached_check_llm,
    cached_compare_bandits,
    cached_info,
    cached_models_list,
    cached_ohlcv,
    cached_search,
    current_provider,
)
from ui.style import QUOTES, quote_html, section, signal_badge_html, ticker_html


def render() -> None:
    """Tab 1 – Analyse & Training."""
    # ── A: Suchleiste ────────────────────────────────────────────────────────
    section("🔍 Aktiensuche  –  WKN, ISIN, Name oder Ticker")
    # st.form: Enter im Textfeld löst die Suche aus (erster Submit-Button)
    with st.form("search_form", border=False):
        row_a, row_b, row_c, row_d = st.columns([4, 1, 1, 1])
        with row_a:
            q = st.text_input(
                "Suche",
                placeholder="z.B. BMW, 519000, Apple, SAP.DE",
                key="search_q",
                label_visibility="collapsed",
            )
        with row_b:
            do_search = st.form_submit_button("🔍 Suchen", use_container_width=True)
        with row_c:
            st.session_state.period = st.selectbox(
                "Zeitraum",
                ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                index=3,
                key="period_sel",
                label_visibility="collapsed",
            )
        with row_d:
            do_load = st.form_submit_button("📥 Laden", use_container_width=True, type="primary")

    # Suche ausführen
    if do_search and q:
        with st.spinner("Suche läuft…"):
            results = cached_search(q)
        if results:
            st.session_state.search_results = results
            st.session_state.search_selected_idx = 0
            st.session_state.search_query = q
        else:
            st.warning("Keine Ergebnisse gefunden.")

    # Autocomplete-Dropdown
    if st.session_state.search_results:
        opts = [
            f"{r.get('symbol', '?')} – {r.get('name', '')[:40]} ({r.get('exchange', '')})"
            for r in st.session_state.search_results
        ]
        idx = st.selectbox(
            "Ergebnisse",
            range(len(opts)),
            format_func=lambda i: opts[i],
            key="search_sel",
            label_visibility="collapsed",
        )
        st.session_state.search_selected_idx = idx

    # Daten laden
    if do_load:
        # Ticker bestimmen: aus Suchergebnis oder direkt aus Text-Input
        if st.session_state.search_results and st.session_state.search_query == q:
            sel = st.session_state.search_results[st.session_state.search_selected_idx]
            ticker_to_load = sel["symbol"]
        elif q:
            ticker_to_load = q.strip().upper()
        else:
            ticker_to_load = ""

        if ticker_to_load:
            # Nur den Parquet-Cache DIESES Tickers invalidieren (frische Daten),
            # statt den kompletten Streamlit-Cache aller Ticker zu leeren
            invalidate_cache(ticker_to_load, st.session_state.period)
            cached_ohlcv.clear()
            with st.spinner(f"Lade {ticker_to_load}…"):
                df_new = cached_ohlcv(ticker_to_load, st.session_state.period)
            if df_new.empty:
                st.error(df_new.attrs.get("error", "Fehler beim Laden der Daten."))
            else:
                # Tatsächlich geladener Ticker (kann nach .DE-Fallback abweichen)
                actual_ticker = df_new.attrs.get("symbol", ticker_to_load)
                st.session_state.ticker = actual_ticker
                st.session_state.df = df_new
                st.session_state.info = cached_info(actual_ticker)
                st.session_state.prediction = None
                st.session_state.analysis_text = ""
                st.session_state.sentiment_result = None
                st.session_state.explanation_text = ""
                st.session_state.explanation_error = ""
                st.session_state.data_quality = get_data_quality_report(df_new)
                # Trainings-/Trading-Ergebnisse gehören zum vorigen Ticker –
                # sonst bleiben sie unter dem neuen Ticker sichtbar, ohne
                # Hinweis, dass sie veraltet/falsch zugeordnet sind.
                st.session_state.cycle_result = None
                st.session_state.auto_result = None
                st.session_state.auto_trade_result = None
                # Verlauf aktualisieren
                hist = st.session_state.history
                if actual_ticker not in hist:
                    hist.append(actual_ticker)
                if len(hist) > 10:
                    st.session_state.history = hist[-10:]
                st.toast(f"📊 {len(df_new)} Kerzen geladen", icon="✅")
                st.rerun()
        else:
            st.toast("Bitte WKN, Ticker oder Firmenname eingeben.", icon="🚨")
            st.error("Bitte WKN, Ticker oder Firmenname eingeben.")

    # ── B: Chart + Controls ──────────────────────────────────────────────────
    if st.session_state.df is not None:
        df: pd.DataFrame = st.session_state.df
        ticker: str = st.session_state.ticker
        info: dict = st.session_state.info

        # Kopfzeile
        name = info.get("name", ticker)
        curr = info.get("currency", "")
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
        chg = (last - prev) / prev * 100 if prev else 0
        chg_c = GREEN if chg >= 0 else RED
        # Data Quality Badge (inline mit dem Preis-Header)
        dq = st.session_state.data_quality or get_data_quality_report(df)
        if dq["ok"]:
            dq_badge = (
                '<span title="Datenqualität: keine Auffälligkeiten" '
                'style="font-size:13px;margin-left:10px;cursor:default;">✅ Datenqualität</span>'
            )
        else:
            issues_html = html.escape("\n".join(dq["issues"]), quote=True)
            dq_badge = (
                f'<span title="Datenqualität: {issues_html}" '
                f'style="font-size:13px;margin-left:10px;cursor:default;color:#f0b429;">'
                f"⚠️ Datenqualität</span>"
            )

        st.markdown(
            f'<div style="margin:8px 0 4px;">'
            f'<span style="font-family:IBM Plex Mono;font-size:22px;'
            f'font-weight:700;color:#c9d1d9;">{html.escape(str(name))}</span>&nbsp;&nbsp;'
            f'<span style="color:#8b949e;font-size:14px;">{html.escape(ticker)} · {html.escape(str(curr))}</span>'
            f'&nbsp;&nbsp;<span style="font-family:IBM Plex Mono;font-size:20px;'
            f'font-weight:700;color:#00ff88;">{last:.2f}</span>'
            f'&nbsp;<span style="color:{chg_c};font-size:14px;">{chg:+.2f}%</span>'
            f"{dq_badge}"
            f"</div>"
            f'<div style="margin:0 0 10px;font-size:11px;color:#8b949e;">'
            f"{dq['first_date']} – {dq['last_date']} &nbsp;·&nbsp; {len(df)} Kerzen"
            f"</div>",
            unsafe_allow_html=True,
        )
        if not dq["ok"]:
            with st.expander("⚠️ Datenqualitäts-Hinweise", expanded=False):
                for issue in dq["issues"]:
                    st.warning(issue)

        col_left, col_right = st.columns([1, 2])

        with col_left:
            section("⚙️ Konfiguration")
            # Modell-Auswahl
            running_models = cached_models_list()
            model_opts = running_models if running_models else AVAILABLE_MODELS
            try:
                def_idx = model_opts.index(st.session_state.model)
            except ValueError:
                def_idx = 0
            st.session_state.model = st.selectbox(
                "🤖 KI-Modell",
                model_opts,
                index=def_idx,
                key="model_sel",
            )
            # Methode
            st.session_state.method = st.selectbox(
                "📐 Analyse-Methode",
                ANALYSIS_METHODS,
                index=ANALYSIS_METHODS.index(st.session_state.method)
                if st.session_state.method in ANALYSIS_METHODS
                else 0,
                key="method_sel",
            )
            # Schnell-Aktionen
            st.divider()
            section("⚡ Schnellaktionen")

            if st.button("🔮 Signal berechnen", use_container_width=True, key="btn_quick_pred"):
                with st.spinner("Berechne Signal…"):
                    _sent_score = (st.session_state.sentiment_result or {}).get("score", 0.0)
                    pred = predict(
                        ticker,
                        df,
                        method=st.session_state.method,
                        ml_bundle=load_model(ticker),
                        training_state=load_state(ticker),
                        sentiment_score=_sent_score,
                    )
                    st.session_state.prediction = pred
                    st.session_state.last_pred_ticker = ticker
                    st.session_state.last_pred_signal = pred.signal
                    st.session_state.last_pred_conf = pred.confidence
                    st.session_state.last_pred_time = time.strftime("%H:%M:%S")
                st.rerun()

            if st.session_state.prediction:
                pred = st.session_state.prediction
                st.markdown(
                    f"{signal_badge_html(pred.signal)}"
                    f'&nbsp;<span style="color:#8b949e;font-size:12px;">'
                    f"{pred.confidence:.0%}</span>",
                    unsafe_allow_html=True,
                )
                if pred.summary:
                    st.caption(pred.summary[:120])

            # KI-Analyse (Sentiment + Erklärung)
            llm_ok = cached_check_llm(current_provider())
            if llm_ok:
                if st.button(
                    "🤖 Sentiment & Erklärung", use_container_width=True, key="btn_quick_ai"
                ):
                    pred = st.session_state.prediction or predict(
                        ticker,
                        df,
                        method=st.session_state.method,
                        ml_bundle=load_model(ticker),
                        training_state=load_state(ticker),
                        sentiment_score=(st.session_state.sentiment_result or {}).get("score", 0.0),
                    )
                    with st.spinner("Analysiere News-Sentiment…"):
                        try:
                            from modules.llm_providers import get_provider

                            _prov = get_provider(current_provider())
                            sent = analyze_news(
                                ticker,
                                n=5,
                                provider=_prov,
                                model_name=st.session_state.model,
                            )
                            st.session_state.sentiment_result = sent
                        except Exception as _e:
                            st.session_state.sentiment_result = {
                                "score": 0.0,
                                "n_news": 0,
                                "samples": [],
                                "error": str(_e),
                            }
                    sent = st.session_state.sentiment_result or {}
                    with st.spinner("Erstelle Erklärung…"):
                        try:
                            ml_b = load_model(ticker)
                            feat_dict: dict = {}
                            imp_dict: dict = {}
                            if ml_b and len(df) > 0:
                                from modules.predictor import _build_features

                                fdf = _build_features(df, sent.get("score", 0.0))
                                if len(fdf) > 0:
                                    feat_dict = fdf.iloc[-1].to_dict()
                                imp_raw = getattr(ml_b.get("model"), "feature_importances_", None)
                                fn = ml_b.get("feature_names", list(feat_dict.keys()))
                                if imp_raw is not None and len(imp_raw) == len(fn):
                                    imp_dict = dict(zip(fn, imp_raw.tolist()))
                            expl = explain_decision(
                                features=feat_dict,
                                prediction=pred.signal,
                                sentiment_score=sent.get("score", 0.0),
                                feature_importances=imp_dict,
                                provider=_prov,
                                model_name=st.session_state.model,
                            )
                            st.session_state.explanation_text = expl
                            st.session_state.explanation_error = ""
                        except Exception as _e:
                            st.session_state.explanation_text = ""
                            st.session_state.explanation_error = str(_e)
            else:
                st.warning("LLM offline → Tab ⚙️")

            # Ergebnis-Anzeige: Sentiment-Karte + Erklärung
            sent = st.session_state.sentiment_result
            expl = st.session_state.explanation_text
            expl_err = st.session_state.get("explanation_error", "")
            if sent or expl or expl_err:
                st.divider()
                section("🧠 KI-Analyse")
                if sent and sent.get("error"):
                    st.warning(f"Sentiment-Analyse fehlgeschlagen: {sent['error']}")
                    sent = None
                if expl_err:
                    st.error(f"Erklärung fehlgeschlagen: {expl_err}")
                if sent:
                    score = sent.get("score", 0.0)
                    n_news = sent.get("n_news", 0)
                    score_color = (
                        "#00ff88" if score > 0.2 else "#ff4444" if score < -0.2 else "#f0b429"
                    )
                    st.markdown(
                        f'<div class="sm-card" style="margin-bottom:8px;">'
                        f'<div class="sm-label">News-Sentiment ({n_news} Headlines)</div>'
                        f'<div style="font-family:IBM Plex Mono;font-size:22px;'
                        f'font-weight:700;color:{score_color};margin-top:4px;">'
                        f"{score:+.2f}</div>"
                        f'<div class="sm-label" style="margin-top:2px;">'
                        f"Skala -1 (sehr negativ) bis +1 (sehr positiv)</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                if expl:
                    st.markdown(
                        quote_html(expl),
                        unsafe_allow_html=True,
                    )

        with col_right:
            section("📈 Candlestick-Chart")
            show_sma = st.checkbox("SMAs", value=True, key="chk_sma")
            show_vol = st.checkbox("Volumen", value=True, key="chk_vol")
            st.plotly_chart(
                candlestick_pro(df, ticker, show_volume=show_vol, show_sma=show_sma),
                width="stretch",
            )
            ind_opts = ["– keiner –", "RSI", "MACD", "Bollinger Bands"]
            ind_sel = st.selectbox("Indikator", ind_opts, key="ind_sel")
            if ind_sel != "– keiner –":
                fig_ind = indicator_fig(df, ind_sel)
                if fig_ind:
                    st.plotly_chart(fig_ind, width="stretch")

    else:
        # Onboarding wenn noch keine Daten geladen
        st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        for col, icon, head, txt in [
            (
                c1,
                "📈",
                "Analysieren",
                "KI-gestützte Analyse mit lokalen LLMs. Keine Cloud, keine API-Keys.",
            ),
            (
                c2,
                "🎓",
                "Trainieren",
                "Trainiere Vorhersagemodelle und verfolge deren Genauigkeit im Zeitverlauf.",
            ),
            (
                c3,
                "🏎️",
                "Paper-Trading",
                f"Starte mit {DEFAULT_BUDGET_EUR:,.0f}€ virtuellem Kapital und jage den Lambo.",
            ),
        ]:
            with col:
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;padding:24px;">'
                    f'<div style="font-size:40px;">{icon}</div>'
                    f'<div style="color:#00ff88;font-weight:700;margin:8px 0;">{head}</div>'
                    f'<div style="color:#8b949e;font-size:13px;">{txt}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── C: Training-Sektion ──────────────────────────────────────────────────
    if st.session_state.df is not None:
        st.divider()
        section("🎓 Training & Backtesting")

        state = load_state(st.session_state.ticker)
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
                btn_cycle = st.button(
                    "▶ Zyklus starten",
                    use_container_width=True,
                    type="primary",
                    key="btn_llm_cycle",
                )
                btn_ml = st.button(
                    "📈 ML-Modell trainieren",
                    use_container_width=True,
                    key="btn_ml_train",
                    help=(
                        "Trainiert das sklearn-GBM-Modell (TimeSeriesSplit-CV "
                        "mit Embargo) und speichert es für '🔮 Signal berechnen'."
                    ),
                )
                if btn_ml:
                    try:
                        with st.spinner("Trainiere GBM-Modell (5-Fold-CV)…"):
                            _ml_state = train_ml_model(st.session_state.ticker, df)
                        st.toast(
                            f"ML-Training fertig – Balanced Accuracy {_ml_state['accuracy']:.1%}",
                            icon="✅",
                        )
                    except ValueError as _e:
                        st.error(str(_e))
            with col_r:
                if btn_cycle:
                    if not cached_check_llm(current_provider()):
                        st.error("LLM offline – Provider im Tab ⚙️ prüfen.")
                    else:
                        anim_slot = st.empty()
                        quote = random.choice(QUOTES)
                        anim_slot.markdown(
                            ticker_html()
                            + f'<div class="sm-quote">"<span class="sm-pulse">⬛</span> '
                            f"KI analysiert {html.escape(st.session_state.ticker)}… · "
                            f'{html.escape(quote)}"</div>',
                            unsafe_allow_html=True,
                        )
                        with st.spinner(f"Trainingszyklus ({t_method})…"):
                            result = trainer.run_training_cycle(
                                st.session_state.ticker,
                                t_method,
                                st.session_state.model,
                                provider=current_provider(),
                            )
                        anim_slot.empty()
                        if result.get("error"):
                            st.error(result["error"])
                        else:
                            cycle = result.get("cycle", 0)
                            # Easter Egg einmalig beim Abschluss auswerten
                            if ENABLE_EASTER_EGGS:
                                result["_egg"] = check_easter_egg(
                                    {
                                        "cycles": cycle,
                                        "previous_cycles": st.session_state.prev_cycles,
                                        "accuracy": result.get("overall_accuracy", 0.0),
                                        "total_return_pct": None,
                                    }
                                )
                            st.session_state.prev_cycles = cycle

                            # Ergebnis persistieren – überlebt so den Rerun
                            st.session_state.cycle_result = result
                            st.session_state.last_pred_ticker = st.session_state.ticker
                            st.session_state.last_pred_signal = result.get("prediction", "?")
                            st.session_state.last_pred_conf = result.get("confidence", 0.0)
                            st.session_state.last_pred_time = time.strftime("%H:%M:%S")
                            st.rerun()

                # Persistiertes Ergebnis rendern (auch nach Rerun sichtbar)
                _cyc = st.session_state.cycle_result
                if _cyc and not _cyc.get("error"):
                    ok = _cyc.get("correct", False)
                    pred_sig = _cyc.get("prediction", "?")
                    conf = _cyc.get("confidence", 0.0)
                    m_acc = _cyc.get("method_accuracy", 0.0)
                    o_acc = _cyc.get("overall_accuracy", 0.0)

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Vorhersage", pred_sig, "✅ Korrekt" if ok else "❌ Falsch")
                    mc2.metric("Konfidenz", f"{conf:.0%}")
                    mc3.metric("Methoden-Acc", f"{m_acc:.1%}")
                    mc4.metric("Gesamt-Acc", f"{o_acc:.1%}")

                    if _cyc.get("reasoning"):
                        st.markdown(
                            quote_html(_cyc["reasoning"][:300]),
                            unsafe_allow_html=True,
                        )
                    egg = _cyc.pop("_egg", None)
                    if egg:
                        if CONFETTI_MARKER in egg:
                            st.balloons()
                            egg = egg.replace(CONFETTI_MARKER, "")
                        st.info(egg)
                else:
                    st.markdown(
                        quote_html(random.choice(QUOTES)),
                        unsafe_allow_html=True,
                    )

        # ── Auto-Modus ───────────────────────────────────────────────────────
        with sub2:
            col_x, col_y = st.columns([1, 2])
            with col_x:
                n_auto = st.slider("Zyklen", 1, 20, 3, key="auto_n")

                # Bandit-Auswahl
                bandit_idx = (
                    list(_BANDIT_NAMES).index(st.session_state.bandit_algo)
                    if st.session_state.bandit_algo in _BANDIT_NAMES
                    else 0
                )
                selected_bandit = st.selectbox(
                    "Bandit-Algorithmus",
                    list(_BANDIT_NAMES),
                    index=bandit_idx,
                    key="bandit_sel",
                    help=(
                        "UCB1: klassisch, für stabile Märkte.\n"
                        "D-UCB: gewichtet neue Rewards höher, besser bei Regime-Wechseln.\n"
                        "Thompson: Bayesianisch, adaptiv ohne Tuning."
                    ),
                )
                st.session_state.bandit_algo = selected_bandit

                btn_auto = st.button(
                    "🔄 Auto starten", use_container_width=True, type="primary", key="btn_auto"
                )
            with col_y:
                if btn_auto:
                    if not cached_check_llm(current_provider()):
                        st.error("LLM offline – Provider im Tab ⚙️ prüfen.")
                    else:
                        st.markdown(ticker_html(), unsafe_allow_html=True)
                        last_res = None
                        log_lines: list[str] = []
                        with st.status(
                            f"Auto-Training: {n_auto} Zyklen für "
                            f"{st.session_state.ticker} [{selected_bandit}]",
                            expanded=True,
                        ) as status:
                            for i in range(n_auto):
                                status.update(label=f"Zyklus {i + 1}/{n_auto} läuft…")
                                res = trainer.auto_mode(
                                    st.session_state.ticker,
                                    st.session_state.model,
                                    bandit_name=selected_bandit,
                                    provider=current_provider(),
                                )
                                last_res = res
                                if res.get("error"):
                                    line = f"❌ Zyklus {i + 1}: {res['error']}"
                                    st.write(line)
                                    log_lines.append(line)
                                    break
                                ok_sym = "✅" if res.get("correct") else "❌"
                                line = (
                                    f"{ok_sym} Zyklus {i + 1} · "
                                    f"**{res.get('prediction', '?')}** · "
                                    f"Methode: {res.get('method', '?')} · "
                                    f"Acc: {res.get('overall_accuracy', 0):.1%}"
                                )
                                st.write(line)
                                log_lines.append(line)
                            status.update(label="Fertig!", state="complete")

                        egg = None
                        if last_res and not last_res.get("error"):
                            if ENABLE_EASTER_EGGS:
                                egg = check_easter_egg(
                                    {
                                        "cycles": last_res.get("cycle", 0),
                                        "previous_cycles": st.session_state.prev_cycles,
                                        "accuracy": last_res.get("overall_accuracy"),
                                        "total_return_pct": None,
                                    }
                                )
                            st.session_state.prev_cycles = last_res.get("cycle", 0)
                        # Protokoll persistieren – überlebt so den Rerun
                        st.session_state.auto_result = {
                            "log": log_lines,
                            "egg": egg,
                            "bandit": selected_bandit,
                        }
                        st.rerun()

                # Persistiertes Protokoll rendern (auch nach Rerun sichtbar)
                _auto = st.session_state.auto_result
                if _auto and _auto.get("log"):
                    with st.expander(
                        f"📋 Letzter Auto-Lauf [{_auto.get('bandit', '?')}]",
                        expanded=True,
                    ):
                        for line in _auto["log"]:
                            st.write(line)
                    egg = _auto.pop("egg", None)
                    if egg:
                        if CONFETTI_MARKER in egg:
                            st.balloons()
                            egg = egg.replace(CONFETTI_MARKER, "")
                        st.info(egg)

                # Bandit A/B-Vergleich (wenn genug History vorhanden)
                state_now = load_state(st.session_state.ticker)
                _hist = state_now.get("accuracy_history", [])
                if len(_hist) >= 6:
                    st.divider()
                    section("📊 Bandit-Vergleich (A/B Replay)")
                    with st.spinner("Berechne Vergleich…"):
                        _cmp = cached_compare_bandits(_hist)
                    if _cmp["figure"].data:
                        st.plotly_chart(_cmp["figure"], width="stretch")
                        fr = _cmp.get("final_rewards", {})
                        _cr1, _cr2, _cr3 = st.columns(3)
                        _cr1.metric("UCB1 Gesamt", f"{fr.get('UCB1', 0):.1f}")
                        _cr2.metric("D-UCB Gesamt", f"{fr.get('D-UCB', 0):.1f}")
                        _cr3.metric("Thompson Gesamt", f"{fr.get('Thompson', 0):.1f}")
                elif len(_hist) > 0:
                    st.caption(f"A/B-Vergleich ab 6 Zyklen verfügbar ({len(_hist)}/6).")

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
                    "Startkapital (€)",
                    value=DEFAULT_BUDGET_EUR,
                    step=1000.0,
                    key="bt_budget",
                )
            st.warning(
                "⚠️ **Survivorship Bias:** yfinance enthält nur derzeit gelistete Aktien. "
                "Insolvente oder delistete Titel fehlen vollständig – Backtest-Performance ist "
                "daher optimistisch verzerrt. Reale Performance typischerweise **1–3 % p.a. niedriger**.",
                icon=None,
            )
            if st.button("▶ Backtest starten", use_container_width=True, key="btn_bt"):
                fn = SIGNAL_FUNCTIONS.get(bt_method)
                if not fn:
                    st.toast(f"Methode '{bt_method}' nicht verfügbar.", icon="🚨")
                    st.error(f"Methode '{bt_method}' nicht verfügbar.")
                else:
                    signals: dict = {}
                    failed = 0
                    df_bt = st.session_state.df
                    n_bars = len(df_bt) - 50
                    bt_bar = st.progress(0.0, text="Berechne Signale…")
                    for j, i in enumerate(range(50, len(df_bt))):
                        try:
                            sig, _ = fn(df_bt.iloc[: i + 1])
                            signals[df_bt.index[i]] = sig
                        except Exception:
                            signals[df_bt.index[i]] = "HALTEN"
                            failed += 1
                        if j % 25 == 0:
                            bt_bar.progress(
                                (j + 1) / max(n_bars, 1),
                                text=f"Berechne Signale… {j + 1}/{n_bars}",
                            )
                    bt_bar.empty()
                    sig_s = pd.Series(signals)
                    with st.spinner("Simuliere Trades…"):
                        result = backtest_signals(
                            st.session_state.ticker,
                            df_bt,
                            sig_s,
                            initial_cash=bt_budget,
                        )
                    # Ergebnis persistieren – überlebt jede weitere Interaktion
                    st.session_state.backtest_result = {
                        "result": result,
                        "method": bt_method,
                        "budget": bt_budget,
                        "failed": failed,
                        "ticker": st.session_state.ticker,
                        "index": df_bt.index,
                    }

            # Persistiertes Backtest-Ergebnis rendern
            _bt = st.session_state.backtest_result
            if _bt:
                result = _bt["result"]
                bt_m = _bt["method"]
                bt_b = _bt["budget"]
                st.caption(f"Backtest: {_bt['ticker']} · {bt_m} · Startkapital {bt_b:,.0f} €")
                if _bt.get("failed"):
                    st.warning(
                        f"{_bt['failed']} Signal-Berechnungen fehlgeschlagen – "
                        f"diese Bars wurden als HALTEN gewertet."
                    )
                # Kompakte KPI-Zeile
                bc1, bc2, bc3, bc4, bc5 = st.columns(5)
                bc1.metric("Rendite", f"{result.total_return_pct:+.2f}%")
                bc2.metric("Buy & Hold", f"{result.buy_and_hold_pct:+.2f}%")
                bc3.metric("Win-Rate", f"{result.win_rate:.0%}")
                bc4.metric("Max Drawdown", f"{result.max_drawdown_pct:.2f}%")
                bc5.metric("Sharpe", f"{result.sharpe_ratio:.2f}")

                if result.equity_curve:
                    eq_idx = _bt["index"][-len(result.equity_curve) :]
                    eq_series = pd.Series(result.equity_curve, index=eq_idx)
                    trades_df = pd.DataFrame(result.trades)
                    ext = compute_metrics(eq_series, trades_df)

                    # Erweiterte Metriken-Karte
                    st.markdown("**Erweiterte Kennzahlen**")
                    m1, m2, m3, m4, m5, m6 = st.columns(6)
                    m1.metric("Sharpe", f"{ext['sharpe']:.2f}")
                    m2.metric("Sortino", f"{ext['sortino']:.2f}")
                    m3.metric("Calmar", f"{ext['calmar']:.2f}")
                    m4.metric("Max DD Dauer", f"{ext['max_drawdown_duration_days']}T")
                    m5.metric("Profit Faktor", f"{ext['profit_factor']:.2f}")
                    m6.metric("Expectancy", f"{ext['expectancy']:.2f}€")

                    # Equity-Kurve + Underwater-Chart
                    eq_df = pd.DataFrame({"value": result.equity_curve})
                    st.plotly_chart(
                        equity_chart(eq_df, bt_b, f"Equity Curve – {bt_m}"),
                        width="stretch",
                    )
                    st.plotly_chart(
                        underwater_chart(eq_series, f"Drawdown – {bt_m}"),
                        width="stretch",
                    )
                    # CSV-Export: Equity-Kurve + Trades
                    _exp1, _exp2 = st.columns(2)
                    _exp1.download_button(
                        "⬇️ Equity-Kurve (CSV)",
                        eq_series.rename("equity").to_csv().encode(),
                        file_name=f"backtest_{_bt['ticker']}_{bt_m}_equity.csv",
                        mime="text/csv",
                        key="dl_bt_equity",
                    )
                    if not trades_df.empty:
                        _exp2.download_button(
                            "⬇️ Trades (CSV)",
                            trades_df.to_csv(index=False).encode(),
                            file_name=f"backtest_{_bt['ticker']}_{bt_m}_trades.csv",
                            mime="text/csv",
                            key="dl_bt_trades",
                        )

        # ── Trainings-Statistiken ────────────────────────────────────────────
        state = load_state(st.session_state.ticker)
        if state.get("cycles", 0) > 0:
            st.divider()
            section("📊 Trainings-Statistiken")

            s1, s2, s3 = st.columns([1, 1, 2])
            with s1:
                acc = state.get("current_accuracy") or state.get("accuracy") or 0.0
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;">'
                    f'<div class="sm-label">Trainingszyklen</div>'
                    f'<div class="sm-big-num">{state["cycles"]}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with s2:
                best = state.get("best_method") or "–"
                st.markdown(
                    f'<div class="sm-card" style="text-align:center;">'
                    f'<div class="sm-label">Beste Methode</div>'
                    f'<div style="font-family:IBM Plex Mono;font-size:15px;'
                    f'font-weight:700;color:#f0b429;margin-top:8px;">{html.escape(str(best))}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with s3:
                if acc:
                    st.plotly_chart(
                        accuracy_gauge(acc),
                        width="stretch",
                    )

            if state.get("method_scores"):
                st.plotly_chart(
                    method_bars(state["method_scores"]),
                    width="stretch",
                )

            if state.get("insights"):
                section("💡 KI-Erkenntnisse")
                for ins in reversed(state["insights"][-3:]):
                    st.markdown(quote_html(ins), unsafe_allow_html=True)
