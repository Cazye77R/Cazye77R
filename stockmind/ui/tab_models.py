from __future__ import annotations

import html
import math
import os
import re

import pandas as pd
import streamlit as st
from config import (
    APP_TITLE,
    APP_VERSION,
    AVAILABLE_MODELS,
    CACHE_TTL_HOURS,
    DUCB_GAMMA,
    EXPLORATION_CONSTANT,
    LAMBO_PRICE_EUR,
    MODEL_DESCRIPTIONS,
)
from modules.model_manager import (
    download_model,
)

from ui.state import cached_llm_status, cached_models_info, cached_models_list
from ui.style import section, ticker_html


def render() -> None:
    """Tab 3 – Modell-Manager."""
    # ── Provider-Auswahl ─────────────────────────────────────────────────────
    section("🤖 KI-Provider")

    _provider_opts = ["ollama", "nvidia"]
    _default_provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    _default_idx = (
        _provider_opts.index(_default_provider) if _default_provider in _provider_opts else 0
    )

    _selected_provider = st.selectbox(
        "Provider",
        _provider_opts,
        index=_default_idx,
        key="llm_provider_sel",
        help="Wechsel gilt für diese Sitzung. Für dauerhafte Änderung LLM_PROVIDER in .env setzen.",
    )
    # Auswahl lebt in st.session_state["llm_provider_sel"] (siehe current_provider) –
    # bewusst KEIN os.environ-Write, der würde alle Sessions des Prozesses umstellen.

    # ── Provider-Status ───────────────────────────────────────────────────────
    st.divider()
    section("🔌 Status")

    _prov_st = cached_llm_status(_selected_provider)
    running = _prov_st["running"]

    if running:
        model_count = _prov_st.get("model_count", 0)
        st.markdown(
            f'<div class="sm-card-accent">'
            f'<span class="sm-online">● ONLINE</span>'
            f'&nbsp;&nbsp;<span style="color:#8b949e;font-size:12px;">'
            f"{html.escape(str(_prov_st.get('url', '')))} · "
            f"{model_count} Modell(e) verfügbar</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="sm-card" style="border-color:#ff4444;">'
            f'<span class="sm-offline">● OFFLINE / NICHT KONFIGURIERT</span>'
            f'&nbsp;&nbsp;<span style="color:#8b949e;font-size:12px;">'
            f"{html.escape(str(_prov_st.get('error', 'Provider nicht erreichbar.')))}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        _guide = _prov_st.get("install_guide", "")
        if _guide:
            with st.expander("📖 Einrichtungsanleitung"):
                st.markdown(_guide)

    # ── Installierte Modelle (nur Ollama) ─────────────────────────────────────
    st.divider()
    section("📦 Installierte Modelle")

    if _selected_provider == "nvidia":
        st.info(
            "NVIDIA NIM – Modelle werden über die Cloud bereitgestellt. "
            "Kein lokaler Download nötig. "
            "Aktuell konfiguriertes Modell: "
            f"`{os.environ.get('NVIDIA_MODEL', 'meta/llama-3.3-70b-instruct')}`"
        )
    elif running:
        installed = cached_models_info()
        if installed:
            active_model = st.session_state.model
            for m in installed:
                name = m.get("name", "?")
                size = m.get("size_gb", 0)
                descr = m.get("description") or MODEL_DESCRIPTIONS.get(name, "")
                is_active = name == active_model
                badge = '<span class="sm-active-badge">AKTIV</span>' if is_active else ""
                st.markdown(
                    f'<div class="sm-model-row">'
                    f'<span style="font-family:IBM Plex Mono;font-weight:700;'
                    f'color:#c9d1d9;min-width:120px;">{html.escape(str(name))}</span>'
                    f'<span style="color:#8b949e;font-size:12px;min-width:70px;">'
                    f"{size:.1f} GB</span>"
                    f'<span style="color:#8b949e;font-size:12px;flex:1;">'
                    f"{html.escape(str(descr))}</span>"
                    f"{badge}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if st.button("🔄 Modell-Liste aktualisieren", key="btn_refresh_models"):
                st.rerun()
        else:
            st.info("Ollama läuft, aber noch kein Modell installiert.")
    elif _selected_provider != "nvidia":
        st.info("Ollama offline – keine Modelle verfügbar.")

    # ── Download (nur Ollama) ─────────────────────────────────────────────────
    if _selected_provider == "nvidia":
        st.divider()
        st.info(
            "NVIDIA NIM benötigt keinen Modell-Download. "
            "Setze `NVIDIA_API_KEY` in deiner `.env`-Datei um die API zu nutzen."
        )
    else:
        st.divider()
        section("⬇️ Modell herunterladen")

        installed_names = set(cached_models_list()) if running else set()
        download_opts = [m for m in AVAILABLE_MODELS if m not in installed_names]

        if not download_opts:
            st.success("✅ Alle empfohlenen Modelle sind bereits installiert.")
        else:
            dl_col1, dl_col2 = st.columns([2, 1])
            with dl_col1:
                dl_model = st.selectbox(
                    "Modell wählen",
                    download_opts,
                    key="dl_model_sel",
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
                st.markdown(ticker_html(), unsafe_allow_html=True)
                progress_slot = st.empty()
                bar_slot = st.empty()
                done = False
                pct = 0.0
                _pct_re = re.compile(r"(\d{1,3})%")
                try:
                    for line in download_model(dl_model):
                        if not line.strip():
                            continue
                        progress_slot.markdown(
                            f'<div class="sm-card" style="font-family:IBM Plex Mono;'
                            f'font-size:11px;color:#8b949e;">{html.escape(line.strip())}</div>',
                            unsafe_allow_html=True,
                        )
                        # Echten Fortschritt aus der ollama-pull-Ausgabe parsen
                        m = _pct_re.search(line)
                        if m:
                            pct = min(int(m.group(1)) / 100, 1.0)
                        bar_slot.progress(pct, text=f"Lade {dl_model}…")
                        done = True
                except Exception as e:
                    st.toast(f"Download-Fehler: {e}", icon="🚨")
                    st.error(f"Download-Fehler: {e}")

                progress_slot.empty()
                bar_slot.empty()
                if done:
                    cached_models_list.clear()  # Modell-Cache invalidieren → sofortige Anzeige
                    cached_models_info.clear()
                    st.toast(f"{dl_model} erfolgreich heruntergeladen", icon="✅")
                    st.rerun()

    # ── Modell-Vergleichstabelle ──────────────────────────────────────────────
    st.divider()
    section("📊 Modell-Vergleich & Empfehlungen")

    comparison = [
        {
            "Modell": "llama3",
            "Größe (ca.)": "4.7 GB",
            "Stärken": "Ausgewogene Analyse, gutes Deutsch/Englisch",
            "RAM": "8 GB",
            "Empfohlen für": "Standardanalyse, Einsteiger",
            "⭐": "⭐⭐⭐⭐⭐",
        },
        {
            "Modell": "mistral",
            "Größe (ca.)": "4.1 GB",
            "Stärken": "Sehr schnell, effizient, gute Logik",
            "RAM": "8 GB",
            "Empfohlen für": "Viele Auto-Zyklen, schnelles Training",
            "⭐": "⭐⭐⭐⭐",
        },
        {
            "Modell": "phi3",
            "Größe (ca.)": "2.3 GB",
            "Stärken": "Klein & sparsam, überraschend gut",
            "RAM": "4 GB",
            "Empfohlen für": "Schwache Hardware, erste Tests",
            "⭐": "⭐⭐⭐",
        },
        {
            "Modell": "gemma2",
            "Größe (ca.)": "5.4 GB",
            "Stärken": "Googles Modell, strukturierte Ausgaben",
            "RAM": "8 GB",
            "Empfohlen für": "JSON-Parsing, strukturierte Analysen",
            "⭐": "⭐⭐⭐⭐",
        },
        {
            "Modell": "qwen2",
            "Größe (ca.)": "4.4 GB",
            "Stärken": "Mehrsprachig, Mathematik-stärke",
            "RAM": "8 GB",
            "Empfohlen für": "Internationale Aktien, Quantanalyse",
            "⭐": "⭐⭐⭐⭐",
        },
    ]
    comp_df = pd.DataFrame(comparison)
    st.dataframe(comp_df, width="stretch", hide_index=True)

    # ── Aktive Konfiguration ──────────────────────────────────────────────────
    st.divider()
    section("🔧 Aktive Konfiguration")
    st.markdown(
        '<div class="sm-card">'
        '<table style="width:100%;font-size:13px;color:#c9d1d9;">'
        f'<tr><td style="color:#8b949e;width:220px;">Explorations-Konstante (UCB)</td>'
        f'<td><code style="color:#00ff88;">{EXPLORATION_CONSTANT}</code>&nbsp;'
        f'<span style="color:#8b949e;font-size:11px;">(sqrt(2) = {math.sqrt(2):.4f})</span></td></tr>'
        f'<tr><td style="color:#8b949e;">D-UCB Gamma (γ)</td>'
        f'<td><code style="color:#00ff88;">{DUCB_GAMMA}</code>&nbsp;'
        f'<span style="color:#8b949e;font-size:11px;">Discount-Faktor; 1=kein Vergessen</span></td></tr>'
        f'<tr><td style="color:#8b949e;">Ollama Host</td>'
        f"<td><code>{html.escape(os.getenv('OLLAMA_HOST', 'http://localhost:11434'))}</code></td></tr>"
        f'<tr><td style="color:#8b949e;">Cache TTL</td>'
        f"<td><code>{CACHE_TTL_HOURS} h</code></td></tr>"
        f'<tr><td style="color:#8b949e;">Log-Level</td>'
        f"<td><code>{html.escape(os.getenv('LOG_LEVEL', 'INFO'))}</code></td></tr>"
        "</table>"
        '<div style="margin-top:8px;color:#8b949e;font-size:11px;">'
        "Werte aus <code>.env</code> änderbar – App neu starten zum Übernehmen."
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ── Über StockMind ────────────────────────────────────────────────────────
    st.divider()
    section(f"ℹ️ Über {APP_TITLE} v{APP_VERSION}")
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
        f"{LAMBO_PRICE_EUR:,.0f} €</td></tr>"
        f"</table>"
        f'<div style="margin-top:12px;color:#8b949e;font-size:11px;">'
        f"⚠️ StockMind ist ein experimentelles Bildungs- und Unterhaltungstool. "
        f"Alle Analysen und Signale stellen keine Anlageberatung dar."
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
