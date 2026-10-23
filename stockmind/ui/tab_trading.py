from __future__ import annotations

import pandas as pd
import streamlit as st
from config import (
    ANALYSIS_METHODS,
    ENABLE_EASTER_EGGS,
    MAX_CORRELATED_EXPOSURE_PCT,
)
from modules.backtester import (
    PaperTrader,
    lambo_display,
    lambo_progress,
)
from modules.easter_eggs import (
    CURRENCY_UNLOCK_CLICKS,
    get_currency_display,
    get_trade_count_egg,
)
from modules.risk_manager import _ticker_market

from ui.charts import GREEN, RED, equity_chart
from ui.state import cached_check_llm, cached_ohlcv, current_provider
from ui.style import section, ticker_html


def render() -> None:
    """Tab 2 – Paper Trading."""
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
        d = cached_ohlcv(sym, "5d")
        current_prices[sym] = (
            float(d["Close"].iloc[-1])
            if not d.empty
            else pt_state.positions[sym].get("avg_price", 0)
        )

    summary = pt.get_portfolio_summary(current_prices)

    # ── Portfolio KPIs ────────────────────────────────────────────────────────
    section("💼 Portfolio-Übersicht")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    # Gesamtwert – klickbarer Button (Easter-Egg Klick-Counter)
    _currency = st.session_state.selected_currency
    _display_val = get_currency_display(summary["total_value"], _currency)
    _ret_color = GREEN if summary["total_return_pct"] >= 0 else RED
    _ret_sign = "+" if summary["total_return_pct"] >= 0 else ""
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
            f"{_ret_sign}{summary['total_return_pct']:.2f}%</span>",
            unsafe_allow_html=True,
        )

    kpi2.metric("Cash", f"{summary['cash']:,.2f} €")
    kpi3.metric("Positionen", f"{summary['position_value']:,.2f} €")
    kpi4.metric(
        "Realisiert",
        f"{summary['realized_pnl']:+,.2f} €",
        delta_color="normal",
    )
    win_r = summary.get("win_rate", 0.0)
    n_sell = summary.get("num_sell_trades", 0)
    kpi5.metric("Win-Rate", f"{win_r:.0%}" if n_sell else "–", f"{n_sell} Trades")

    # Währungsauswahl nach Unlock
    if ENABLE_EASTER_EGGS and st.session_state.currency_unlocked:
        st.markdown(
            '<div class="sm-card-accent">'
            "🎉 <strong>Easter Egg freigeschaltet!</strong> "
            "Die geheime Währungsauswahl ist jetzt in der Sidebar verfügbar."
            "</div>",
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
        section(f"🏎️ Lambo-O-Meter  ·  {lambo_display(summary['total_value'])}")
        st.progress(min(lv_pct / 100, 1.0), text=lv_msg)

    # ── Performance-Chart ─────────────────────────────────────────────────────
    perf_df = pt.get_performance_chart()
    if len(perf_df) > 1:
        st.plotly_chart(
            equity_chart(perf_df, float(pt_state.start_budget), "Portfolio-Wert über Zeit"),
            width="stretch",
        )

    # ── Offene Positionen ─────────────────────────────────────────────────────
    st.divider()
    section("📋 Offene Positionen")
    if summary.get("positions"):
        pos_df = pd.DataFrame(summary["positions"])
        st.dataframe(pos_df, width="stretch", hide_index=True)
    else:
        st.markdown(
            '<div class="sm-card" style="text-align:center;color:#8b949e;'
            'padding:24px;">Keine offenen Positionen.</div>',
            unsafe_allow_html=True,
        )

    # ── Trading-Tabs ──────────────────────────────────────────────────────────
    st.divider()
    t_manual, t_auto, t_hist, t_reset = st.tabs(
        ["🖱️ Manuelle Order", "🤖 Auto-Trade", "📋 Trade-Historie", "⚠️ Reset"]
    )

    with t_manual:
        st.caption(
            "Simulierter Handel – kein echtes Geld. Kauf/Verkauf wird sofort zum aktuellen Schlusskurs ausgeführt."
        )
        if st.session_state.df is not None and st.session_state.ticker:
            ticker_pt = st.session_state.ticker
            df_pt = st.session_state.df
            price_pt = float(df_pt["Close"].iloc[-1])
            pt_state_now = pt.load()

            ma1, ma2, ma3, ma4 = st.columns(4)
            with ma1:
                pt_dir = st.selectbox("Richtung", ["BUY", "SELL"], key="pt_dir")
            with ma2:
                pt_frac = st.slider("Cash-Anteil", 0.05, 1.0, 0.2, 0.05, key="pt_frac")
            with ma3:
                st.metric("Kurs", f"{price_pt:.2f} €")
            with ma4:
                invest = pt_state_now.cash * pt_frac
                qty_est = invest / price_pt if price_pt > 0 else 0
                st.metric("Menge (ca.)", f"{qty_est:.4f}")

            # Live-Vorschau des Risk-Manager-Limits für BUY-Orders: der
            # Slider erlaubt bis zu 100% Cash-Anteil, aber place_order()
            # lehnt Orders ab, die das korrelierte Exposure-Limit je
            # Markt-Gruppe überschreiten (siehe modules/risk_manager.py
            # check_exposure). Diese Warnung zeigt das VOR dem Klick an,
            # statt die Order erst danach mit einer kryptischen
            # Fehlermeldung abzulehnen.
            if pt_dir == "BUY":
                _pos_val_now = sum(
                    p["quantity"] * (p.get("last_price") or p["avg_price"])
                    for p in pt_state_now.positions.values()
                )
                _equity_now = pt_state_now.cash + _pos_val_now
                if _equity_now > 0:
                    _market = _ticker_market(ticker_pt)
                    _already_correlated = sum(
                        p["quantity"] * (p.get("last_price") or p["avg_price"])
                        for sym, p in pt_state_now.positions.items()
                        if _ticker_market(sym) == _market
                    )
                    _order_value = (
                        invest  # Spread/Gebühr sind hier vernachlässigbar für die Vorschau
                    )
                    _correlated_pct = (_already_correlated + _order_value) / _equity_now * 100
                    if _correlated_pct >= MAX_CORRELATED_EXPOSURE_PCT:
                        _max_order_value = max(
                            0.0,
                            _equity_now * MAX_CORRELATED_EXPOSURE_PCT / 100 - _already_correlated,
                        )
                        _max_frac = (
                            min(1.0, _max_order_value / pt_state_now.cash)
                            if pt_state_now.cash > 0
                            else 0.0
                        )
                        st.warning(
                            f"⚠️ Diese Order ({_correlated_pct:.0f}% Exposure in Markt-Gruppe "
                            f"'{_market}') überschreitet das Risk-Manager-Limit von "
                            f"{MAX_CORRELATED_EXPOSURE_PCT:.0f}% und wird beim Kauf abgelehnt. "
                            f"Reduziere den Cash-Anteil auf max. ca. {_max_frac:.0%}."
                        )

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
                    qty = pt_state_now.positions.get(ticker_pt, {}).get("quantity", 0)
                res = pt.place_order(ticker_pt, pt_dir, qty, price_pt, signal=sig_str)
                if res["ok"]:
                    pnl_str = f"{res['pnl']:+.2f} €" if res.get("pnl") else "–"
                    # Toast statt st.success – überlebt den folgenden Rerun
                    st.toast(
                        f"{pt_dir} {res['quantity']:.4f} × {ticker_pt} "
                        f"@ {res['exec_price']:.2f} € · PnL: {pnl_str}",
                        icon="✅",
                    )
                    st.rerun()
                else:
                    st.error(res["error"])
        else:
            st.info("Bitte im Tab **📊 Analyse** zuerst eine Aktie laden.")

    with t_auto:
        st.info(
            "**Wann wird fiktiv gekauft?**  \n"
            "- **KAUF** → KI-Signal = **UP** + Konfidenz **≥ 50 %** + keine offene Position + genug Cash  \n"
            "- **VERKAUF** → KI-Signal = **DOWN** + Konfidenz **≥ 50 %** + offene Position vorhanden  \n"
            "- **HALTEN** → Konfidenz zu niedrig, bereits investiert oder kein Signal"
        )
        if st.session_state.ticker:
            aa1, aa2, aa3 = st.columns(3)
            with aa1:
                at_cycles = st.slider("Zyklen", 1, 10, 3, key="at_cycles")
            with aa2:
                at_invest = st.slider("Invest-Anteil/BUY", 0.05, 0.5, 0.2, 0.05, key="at_invest")
            with aa3:
                at_method = st.selectbox(
                    "Methode",
                    ANALYSIS_METHODS,
                    index=ANALYSIS_METHODS.index("Auto (KI wählt)"),
                    key="at_method",
                )
            _HOLD_LABELS = {
                "HOLD_ALREADY_IN": "Bereits in Position – kein Neukauf",
                "HOLD_LOW_CASH": "Zu wenig Cash",
                "HOLD_NO_POSITION": "Keine Position zum Verkaufen",
                "HOLD_NEUTRAL": "Konfidenz < 50 % – kein Signal",
                "HOLD_RISK_LIMIT": "Risk-Manager: Positionsgröße 0",
                "BUY_FAILED": "Kauf fehlgeschlagen",
                "SELL_FAILED": "Verkauf fehlgeschlagen",
                "SKIP": "Übersprungen (Fehler)",
            }

            def _at_log_line(entry: dict) -> str:
                decision = entry.get("decision", "?")
                pred = entry.get("prediction", "?")
                conf = entry.get("confidence", 0.0)
                price = entry.get("current_price")
                pval = entry.get("portfolio_value")

                if decision == "BUY":
                    icon = "🟢"
                    label = f"**KAUF** · {pred} ({conf:.0%})"
                elif decision == "SELL":
                    icon = "🔴"
                    label = (
                        f"**VERKAUF** · {pred} ({conf:.0%}) · PnL {entry.get('pnl', 0.0):+.2f} €"
                    )
                elif decision == "STOP_LOSS":
                    icon = "🛑"
                    label = f"**STOP-LOSS** · PnL {entry.get('pnl', 0.0):+.2f} €"
                elif decision == "TAKE_PROFIT":
                    icon = "🎯"
                    label = f"**TAKE-PROFIT** · PnL {entry.get('pnl', 0.0):+.2f} €"
                elif decision == "SKIP":
                    icon = "❌"
                    label = f"Fehler: {entry.get('reason', '?')}"
                else:
                    icon = "⚪"
                    label = _HOLD_LABELS.get(decision, f"HALTEN ({decision})")
                    if pred and pred != "?":
                        label += f" · Signal: {pred} ({conf:.0%})"

                price_str = f" · Kurs {price:.2f} €" if price else ""
                pval_str = f" · Portfolio {pval:,.0f} €" if pval else ""
                return f"{icon} Zyklus {entry.get('cycle', '?')}: {label}{price_str}{pval_str}"

            if st.button(
                "🚀 Auto-Trade starten",
                use_container_width=True,
                type="primary",
                key="btn_auto_trade",
            ):
                if not cached_check_llm(current_provider()):
                    st.toast("LLM offline.", icon="🚨")
                    st.error("LLM offline – Provider im Tab ⚙️ prüfen.")
                else:
                    st.markdown(ticker_html(), unsafe_allow_html=True)
                    at_lines: list[str] = []
                    with st.status(
                        f"Auto-Trade: {at_cycles} Zyklen",
                        expanded=True,
                    ) as at_status:
                        # Zyklus für Zyklus in der UI treiben → Live-Feedback
                        # statt eines minutenlangen blockierenden Gesamtaufrufs
                        for _ci in range(at_cycles):
                            at_status.update(
                                label=f"Auto-Trade: Zyklus {_ci + 1}/{at_cycles} läuft…"
                            )
                            _cycle_log = pt.auto_trade(
                                st.session_state.ticker,
                                st.session_state.model,
                                cycles=1,
                                method=at_method,
                                invest_pct=at_invest,
                                provider=current_provider(),
                            )
                            for entry in _cycle_log:
                                entry["cycle"] = _ci + 1
                                line = _at_log_line(entry)
                                st.write(line)
                                at_lines.append(line)
                        at_status.update(label="Auto-Trade abgeschlossen!", state="complete")
                    # Protokoll persistieren – überlebt so den Rerun
                    st.session_state.auto_trade_result = {"log": at_lines}
                    st.rerun()

            # Persistiertes Protokoll rendern (auch nach Rerun sichtbar)
            _at_res = st.session_state.auto_trade_result
            if _at_res and _at_res.get("log"):
                with st.expander("📋 Letzter Auto-Trade-Lauf", expanded=True):
                    for line in _at_res["log"]:
                        st.write(line)

            # ── Strategie-Autopilot (ohne LLM) ─────────────────────────────
            st.divider()
            st.markdown("**🧪 Strategie-Signal ausführen** (aus dem Strategie-Labor)")
            _lab = st.session_state.get("lab_result")
            if not _lab or _lab["ticker"] != st.session_state.ticker or not _lab["res"].current:
                st.caption(
                    "Zuerst im Tab Analyse → Training & Backtesting → 🧪 Strategie-Labor "
                    "die beste Strategie für diesen Wert finden."
                )
            else:
                _cur = _lab["res"].current
                _verdict = _lab["res"].verdict
                st.write(f"Gewählt: **{_cur['strategy']}** → aktuell **{_cur['position_now']}**")
                if _verdict != "besser":
                    st.warning(
                        "Die Auswahl war out-of-sample nicht nachweislich besser als Buy & Hold "
                        f"(Urteil: {_verdict.replace('_', ' ')}). Nur zum Ausprobieren im Paper-Trading."
                    )
                if st.button("▶ Strategie-Signal jetzt handeln", key="btn_strat_trade"):
                    with st.spinner("Berechne Signal…"):
                        _e = pt.strategy_trade(
                            st.session_state.ticker,
                            _cur["key"],
                            _cur["params"],
                            invest_pct=at_invest,
                            label=_cur["strategy"],
                        )
                    st.session_state.auto_trade_result = {"log": [_at_log_line(_e)]}
                    st.rerun()
        else:
            st.info("Bitte zuerst eine Aktie laden.")

    with t_hist:
        if pt_state.trades:
            th = pd.DataFrame(pt_state.trades)
            cols = [
                "timestamp",
                "symbol",
                "direction",
                "quantity",
                "exec_price",
                "pnl",
                "pnl_pct",
                "signal",
            ]
            show = [c for c in cols if c in th.columns]
            st.dataframe(
                th[show].sort_values("timestamp", ascending=False),
                width="stretch",
                hide_index=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn(
                        "Zeitpunkt", format="DD.MM.YYYY HH:mm"
                    ),
                    "symbol": st.column_config.TextColumn("Symbol"),
                    "direction": st.column_config.TextColumn("Richtung"),
                    "quantity": st.column_config.NumberColumn("Stück", format="%.4f"),
                    "exec_price": st.column_config.NumberColumn("Ausführungskurs", format="%.2f €"),
                    "pnl": st.column_config.NumberColumn("PnL", format="%.2f €"),
                    "pnl_pct": st.column_config.NumberColumn("PnL %", format="%.2f %%"),
                    "signal": st.column_config.TextColumn("Signal"),
                },
            )
            st.download_button(
                "⬇️ Trade-Historie (CSV)",
                th[show].to_csv(index=False).encode(),
                file_name=f"trades_{st.session_state.portfolio_name}.csv",
                mime="text/csv",
                key="dl_trades",
            )
        else:
            st.info("Noch keine Trades.")

    with t_reset:
        st.warning("⚠️ Alle Positionen und Trade-Historie werden gelöscht!")
        reset_b = st.number_input(
            "Neues Startkapital (€)",
            value=float(pt_state.start_budget),
            step=1000.0,
            key="pt_reset_budget",
        )
        if st.button("🔄 Portfolio zurücksetzen", type="secondary", key="btn_pt_reset"):
            pt.reset(new_budget=reset_b)
            st.toast(f"Portfolio zurückgesetzt auf {reset_b:,.0f} €.", icon="🔄")
            st.rerun()
