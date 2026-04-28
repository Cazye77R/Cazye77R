"""SecondBrain Agent – Main Streamlit entry point (Home / Hub page)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from core.config import APP_NAME, VERSION

# ---------------------------------------------------------------------------
# Page config – must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS (dark theme)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
/* ── Base ──────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] { background:#1e1e2e; color:#cdd6f4; }
[data-testid="stSidebar"]          { background:#181825; border-right:1px solid #313244; }
[data-testid="stHeader"]           { background:#1e1e2e; }

/* ── Typography ─────────────────────────────────────────── */
h1,h2,h3,h4 { color:#cdd6f4 !important; }
p, li        { color:#a6adc8; }
code         { background:#313244 !important; color:#a6e3a1 !important; border-radius:4px; }
pre          { background:#313244 !important; border-radius:8px; }

/* ── Buttons ────────────────────────────────────────────── */
[data-testid="stButton"] > button {
    border-radius:8px;
    font-size:13px;
    transition:all 0.15s;
}
[data-testid="stButton"] > button[kind="primary"] {
    background:#89b4fa;
    color:#1e1e2e;
    border:none;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    background:#74c7ec;
}
[data-testid="stButton"] > button[kind="secondary"] {
    background:#313244;
    color:#cdd6f4;
    border:1px solid #45475a;
}
[data-testid="stButton"] > button[kind="secondary"]:hover {
    border-color:#89b4fa;
    color:#89b4fa;
}

/* ── Inputs ─────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background:#313244 !important;
    color:#cdd6f4 !important;
    border:1px solid #45475a !important;
    border-radius:8px !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background:#313244;
    border:1px solid #45475a;
    border-radius:8px;
}

/* ── Metrics ────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background:#313244;
    border:1px solid #45475a;
    border-radius:10px;
    padding:12px 16px;
}
[data-testid="stMetricValue"] { color:#89b4fa !important; }

/* ── Expander ───────────────────────────────────────────── */
[data-testid="stExpander"] {
    background:#2a2a3e;
    border:1px solid #45475a;
    border-radius:8px;
}

/* ── Divider ────────────────────────────────────────────── */
hr { border-color:#313244 !important; }

/* ── Sidebar nav labels ─────────────────────────────────── */
[data-testid="stSidebarNav"] span { color:#cdd6f4 !important; font-size:14px; }
[data-testid="stSidebarNav"] a:hover span { color:#89b4fa !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state + resources
# ---------------------------------------------------------------------------
from ui.app_state import init_session_state, get_vault_stats

init_session_state()

# ---------------------------------------------------------------------------
# Sidebar: global vault stats
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"<div style='text-align:center;padding:8px 0 16px;'>"
        f"<span style='font-size:32px;'>🧠</span><br>"
        f"<span style='font-size:15px;font-weight:700;color:#cdd6f4;'>{APP_NAME}</span><br>"
        f"<span style='font-size:11px;color:#6c7086;'>v{VERSION}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Navigation
    st.markdown("**🗺️ Navigation**")
    st.page_link("streamlit_app.py",    label="🏠 Startseite")
    st.page_link("pages/01_Dashboard.py", label="📊 Dashboard")
    st.page_link("pages/02_Notes.py",    label="📝 Notizen")
    st.page_link("pages/03_Search.py",   label="🔍 Suche")
    st.page_link("pages/04_Chat.py",     label="💬 Chat")
    st.page_link("pages/05_Graph.py",    label="🕸️ Graph")
    st.page_link("pages/06_Settings.py", label="⚙️ Einstellungen")

    st.divider()

    try:
        stats = get_vault_stats()
        st.markdown("**📊 Vault**")
        c1, c2 = st.columns(2)
        c1.metric("Notizen", stats.get("total_notes", 0))
        c2.metric("Wörter", f"{stats.get('total_words', 0):,}")
        c3, c4 = st.columns(2)
        c3.metric("Tags", stats.get("total_tags", 0))
        c4.metric("Links", stats.get("total_links", 0))
    except Exception:
        st.caption("Vault-Statistiken nicht verfügbar")

    st.divider()

    try:
        from ai.ollama_client import OllamaClient
        ok = OllamaClient().is_available()
        icon, label = ("🟢", "Ollama verbunden") if ok else ("🔴", "Ollama offline")
        st.markdown(f"{icon} <small style='color:#a6adc8;'>{label}</small>", unsafe_allow_html=True)
    except Exception:
        pass

    # Vault path footer
    try:
        from core.config import VAULT_DIR
        st.markdown(
            f"<div style='margin-top:16px;padding-top:12px;border-top:1px solid #313244;'>"
            f"<p style='color:#45475a;font-size:10px;word-break:break-all;margin:0;'>"
            f"📁 {VAULT_DIR}</p></div>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
st.markdown(
    "<h1 style='margin-bottom:4px;'>🧠 SecondBrain Agent</h1>"
    "<p style='color:#6c7086;'>Dein persönliches KI-gestütztes Wissensmanagementsystem.</p>",
    unsafe_allow_html=True,
)
st.divider()

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("### 📊 Dashboard")
    st.markdown("Vault-Übersicht, Statistiken, Tages-Briefing und Tag-Cloud.")
    st.page_link("pages/01_Dashboard.py", label="Dashboard öffnen →", icon="📊")

with col_b:
    st.markdown("### 📝 Notizen")
    st.markdown("Notizen ansehen, erstellen, bearbeiten und KI-Werkzeuge nutzen.")
    st.page_link("pages/02_Notes.py", label="Notizen öffnen →", icon="📝")

with col_c:
    st.markdown("### 🔍 Suche")
    st.markdown("Semantisch, Volltext oder hybrid über alle Notizen suchen.")
    st.page_link("pages/03_Search.py", label="Suche öffnen →", icon="🔍")

st.divider()

col_d, col_e, col_f = st.columns(3)

with col_d:
    st.markdown("### 💬 Chat")
    st.markdown("Stelle Fragen zu deinem Vault – der Assistent antwortet kontextbezogen.")
    st.page_link("pages/04_Chat.py", label="Chat öffnen →", icon="💬")

with col_e:
    st.markdown("### 🕸️ Wissensgraph")
    st.markdown("Visualisiere Verbindungen zwischen deinen Notizen interaktiv.")
    st.page_link("pages/05_Graph.py", label="Graph öffnen →", icon="🕸️")

with col_f:
    st.markdown("### ⚙️ Einstellungen")
    st.markdown("Vault-Pfad, Ollama-Verbindung, Reindexierung und Backup.")
    st.page_link("pages/06_Settings.py", label="Einstellungen öffnen →", icon="⚙️")

st.divider()
st.markdown("### 🤖 KI-Status")
try:
    from ai.ollama_client import OllamaClient
    client = OllamaClient()
    if client.is_available():
        models = client.list_models()
        st.success(f"Ollama aktiv · {len(models)} Modell(e)")
        mcols = st.columns(min(len(models), 4))
        for i, m in enumerate(models[:4]):
            mcols[i].markdown(f"`{m}`")
    else:
        st.warning("Ollama nicht erreichbar.")
        st.markdown("Starte Ollama mit:\n```\nollama serve\n```")
except Exception as exc:
    st.error(f"Verbindungsfehler: {exc}")
