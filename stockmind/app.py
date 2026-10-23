"""
StockMind – Streamlit Dashboard  (Bloomberg / Trading-Terminal Style)

Einstiegspunkt: Seitenkonfiguration, Session-State, Sidebar und die drei Tabs.
Die eigentliche UI liegt im Paket ``ui/``:

    ui/state.py        gecachte Datenzugriffe, Session-State, Startup-Check
    ui/style.py        CSS und kleine HTML-Helfer (immer mit html.escape!)
    ui/charts.py       Plotly-Figuren
    ui/sidebar.py      Sidebar
    ui/tab_analyse.py  Tab 1 – Analyse & Training
    ui/tab_trading.py  Tab 2 – Paper Trading
    ui/tab_models.py   Tab 3 – Modell-Manager
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from config import APP_ICON, APP_TITLE  # noqa: E402

# MUSS der erste Streamlit-Aufruf sein
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui import sidebar, tab_analyse, tab_models, tab_trading  # noqa: E402
from ui.state import init_session, startup_check  # noqa: E402
from ui.style import inject_css  # noqa: E402

inject_css()
init_session()
startup_check()

sidebar.render_sidebar()

tab1, tab2, tab3 = st.tabs(
    [
        "📊 Analyse & Training",
        "💰 Paper Trading",
        "⚙️ Modell-Manager",
    ]
)

with tab1:
    tab_analyse.render()
with tab2:
    tab_trading.render()
with tab3:
    tab_models.render()
