from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from config import (
    DEFAULT_BUDGET_EUR,
    ORDER_COST_EUR,
    SPREAD_PERCENT,
)
from modules.data_fetcher import (
    fetch_info,
    fetch_ohlcv,
    search_stocks,
)
from modules.easter_eggs import (
    CURRENCIES,
)
from modules.model_manager import (
    get_available_models,
    get_available_models_with_info,
    get_llm_status,
    is_llm_ready,
)
from modules.trainer import (
    compare_bandits,
)

# ─────────────────────────────────────────────────────────────────────────────
# @st.cache_data – vermeidet redundante HTTP/IO-Calls bei jedem Rerun
# Alle externen API-Aufrufe laufen garantiert im Hauptthread (kein Context-Loss).
# ─────────────────────────────────────────────────────────────────────────────


def current_provider() -> str:
    """
    Provider-Auswahl dieser Session (Selectbox in Tab 3); Fallback auf .env.
    Bewusst NICHT über os.environ – das würde alle Sessions des Prozesses ändern.
    """
    return st.session_state.get(
        "llm_provider_sel", os.environ.get("LLM_PROVIDER", "ollama").lower()
    )


@st.cache_data(ttl=60, show_spinner=False)
def cached_check_llm(provider: str) -> bool:
    """Gecachter Verbindungscheck des gewählten Providers (60 s TTL)."""
    return is_llm_ready(provider)


@st.cache_data(ttl=60, show_spinner=False)
def cached_llm_status(provider: str) -> dict:
    """Gecachter Status des gewählten Providers (60 s TTL, Cache-Key = Provider)."""
    return get_llm_status(provider)


@st.cache_data(ttl=60, show_spinner=False)
def cached_models_list() -> list:
    """Gecachte Liste installierter Modell-Namen (60 s TTL)."""
    return get_available_models()


@st.cache_data(ttl=60, show_spinner=False)
def cached_models_info() -> list:
    """Gecachte Modell-Infos inkl. Größe (60 s TTL)."""
    return get_available_models_with_info()


@st.cache_data(ttl=300, show_spinner=False)
def cached_ohlcv(ticker: str, period: str) -> pd.DataFrame:
    """Gecachte OHLCV-Daten (5 min TTL, zusätzlich zum Parquet-Datei-Cache)."""
    return fetch_ohlcv(ticker, period=period)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_info(ticker: str) -> dict:
    """Gecachte Stammdaten/Metadaten (1 h TTL)."""
    return fetch_info(ticker)


@st.cache_data(ttl=120, show_spinner=False)
def cached_search(query: str) -> list:
    """Gecachte Suchergebnisse (2 min TTL)."""
    return search_stocks(query)


@st.cache_data(show_spinner=False)
def cached_compare_bandits(history: list) -> dict:
    """Bandit-A/B-Replay – gecacht auf die History (O(T²), sonst bei jedem Rerun)."""
    from modules.trainer import _METHODS as _avail

    return compare_bandits(history, _avail)


# ─────────────────────────────────────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Startup-Health-Check: Verzeichnisse + Ollama-Status
# ─────────────────────────────────────────────────────────────────────────────


def ensure_data_dirs() -> None:
    """Erstellt fehlende Daten-Ordner beim ersten Start."""
    for d in ["data", "data/cache", "data/training_state", "data/portfolio", "data/logs"]:
        os.makedirs(d, exist_ok=True)


def startup_check() -> None:
    """
    Beim App-Start: Verzeichnisse anlegen, Ollama pruefen, Onboarding anzeigen.
    Wird einmal pro Session ausgefuehrt (session_state.startup_done).
    """
    if st.session_state.get("startup_done"):
        return
    ensure_data_dirs()

    ollama_ok = cached_check_llm(current_provider())
    has_models = False
    if ollama_ok:
        try:
            has_models = len(cached_models_list()) > 0
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


def init_session() -> None:
    defaults: dict = {
        "ticker": "",
        "df": None,
        "info": {},
        "prediction": None,
        "analysis_text": "",
        "sentiment_result": None,
        "explanation_text": "",
        "explanation_error": "",
        "data_quality": None,
        "portfolio_name": "default",
        "model": "llama3",
        "method": "Auto (KI wählt)",
        "bandit_algo": "UCB1",
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
        # Persistierte Ergebnisse (überleben st.rerun)
        "cycle_result": None,
        "auto_result": None,
        "auto_trade_result": None,
        "backtest_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
