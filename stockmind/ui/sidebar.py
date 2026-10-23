from __future__ import annotations

import html

import streamlit as st
from config import (
    APP_ICON,
    APP_TITLE,
    APP_VERSION,
    ENABLE_EASTER_EGGS,
)
from modules.data_fetcher import (
    get_data_quality_report,
)
from modules.easter_eggs import (
    CURRENCIES,
)

from ui.state import cached_info, cached_ohlcv
from ui.style import section, signal_badge_html


def render_sidebar() -> None:
    """Sidebar: Verlauf, letzte Vorhersage, Währungs-Easter-Egg, Trading-Parameter."""
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
        section("📋 Zuletzt analysiert")
        if st.session_state.history:
            for hist_ticker in reversed(st.session_state.history[-5:]):
                if st.button(
                    f"↗ {hist_ticker}", key=f"hist_{hist_ticker}",
                    use_container_width=True,
                ):
                    with st.spinner(f"Lade {hist_ticker}…"):
                        df_h = cached_ohlcv(hist_ticker, st.session_state.period)
                    if df_h.empty:
                        # Fehler sichtbar machen statt still nichts zu tun
                        st.toast(
                            df_h.attrs.get("error", f"Keine Daten für {hist_ticker}."),
                            icon="🚨",
                        )
                    else:
                        st.session_state.ticker = hist_ticker
                        st.session_state.df   = df_h
                        st.session_state.info = cached_info(hist_ticker)
                        st.session_state.prediction    = None
                        st.session_state.analysis_text = ""
                        st.session_state.sentiment_result = None
                        st.session_state.explanation_text = ""
                        st.session_state.explanation_error = ""
                        st.session_state.data_quality = get_data_quality_report(df_h)
                        # Trainings-/Trading-Ergebnisse gehören zum vorigen Ticker –
                        # sonst bleiben sie unter dem neuen Ticker sichtbar, ohne
                        # Hinweis, dass sie veraltet/falsch zugeordnet sind.
                        st.session_state.cycle_result = None
                        st.session_state.auto_result = None
                        st.session_state.auto_trade_result = None
                        st.rerun()
        else:
            st.caption("Noch keine Aktien analysiert.")

        st.divider()

        # ── Letzte Vorhersage ─────────────────────────────────────────────────
        section("🔮 Letzte KI-Vorhersage")
        if st.session_state.last_pred_signal:
            badge = signal_badge_html(st.session_state.last_pred_signal)
            st.markdown(
                f'{badge} &nbsp; '
                f'<span style="color:#8b949e;font-size:11px;">'
                f'{html.escape(st.session_state.last_pred_ticker)} · '
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
            section("💱 Anzeigewährung")
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
