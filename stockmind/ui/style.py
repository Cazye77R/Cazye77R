from __future__ import annotations

import html

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Bloomberg / Trading-Terminal CSS
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
/* ── Global ────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container          { background-color: #0d1117 !important; color: #c9d1d9; }

[data-testid="stSidebar"]       { background-color: #0a0e14 !important;
                                   border-right: 1px solid #1c2128 !important; }

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar              { width: 6px; height: 6px; }
::-webkit-scrollbar-track        { background: #0d1117; }
::-webkit-scrollbar-thumb        { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover  { background: #00ff88; }

/* ── Tabs ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { background: #0a0e14 !important;
                                     border-bottom: 1px solid #1c2128; gap: 2px; }
.stTabs [data-baseweb="tab"]      { background: transparent !important;
                                     color: #8b949e !important;
                                     border-radius: 4px 4px 0 0;
                                     font-family: 'IBM Plex Mono', monospace;
                                     font-size: 13px; padding: 8px 16px; }
.stTabs [aria-selected="true"]    { background: #161b22 !important;
                                     color: #00ff88 !important;
                                     border-top: 2px solid #00ff88 !important; }

/* ── Buttons ───────────────────────────────────────────────────── */
.stButton > button {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace; font-size: 12px;
    transition: all 0.2s;
}
.stButton > button:hover {
    border-color: #00ff88; color: #00ff88;
    box-shadow: 0 0 8px rgba(0,255,136,0.3);
}
.stButton > button[kind="primary"] {
    background: #00ff88; color: #0d1117; border-color: #00ff88;
    font-weight: 700;
}
.stButton > button[kind="primary"]:hover {
    background: #00cc6a; box-shadow: 0 0 12px rgba(0,255,136,0.5);
}

/* ── Inputs ────────────────────────────────────────────────────── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: #0d1117 !important; color: #c9d1d9 !important;
    border: 1px solid #30363d !important; border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace;
}
.stTextInput input:focus { border-color: #00ff88 !important;
                            box-shadow: 0 0 6px rgba(0,255,136,0.3) !important; }

/* ── Metrics ───────────────────────────────────────────────────── */
[data-testid="stMetric"]         { background: #161b22; border: 1px solid #1c2128;
                                     border-radius: 6px; padding: 12px !important; }
[data-testid="stMetricValue"]    { color: #c9d1d9 !important;
                                     font-family: 'IBM Plex Mono', monospace; }
[data-testid="stMetricDelta"]    { font-family: 'IBM Plex Mono', monospace; }

/* ── Progress bar ──────────────────────────────────────────────── */
.stProgress > div > div { background: #00ff88 !important; }

/* ── Dataframe ─────────────────────────────────────────────────── */
[data-testid="stDataFrame"]      { border: 1px solid #1c2128; border-radius: 4px; }

/* ── Divider ───────────────────────────────────────────────────── */
hr { border-color: #1c2128; }

/* ── Custom components ─────────────────────────────────────────── */
.sm-card {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 6px; padding: 16px; margin: 4px 0;
}
.sm-card-accent {
    background: #0d2b1a; border: 1px solid #00ff88;
    border-radius: 6px; padding: 16px; margin: 4px 0;
}
.sm-header {
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; border-bottom: 1px solid #1c2128;
    padding-bottom: 6px; margin-bottom: 12px;
}
.sm-big-num {
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 40px; font-weight: 700; line-height: 1;
    text-shadow: 0 0 20px rgba(0,255,136,0.4);
}
.sm-label {
    color: #8b949e; font-family: 'IBM Plex Mono', monospace;
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
}
.sm-badge-up {
    display: inline-block; background: #0d2b1a; color: #00ff88;
    border: 1px solid #00ff88; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-badge-down {
    display: inline-block; background: #2a0d0d; color: #ff4444;
    border: 1px solid #ff4444; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-badge-neutral {
    display: inline-block; background: #1c2128; color: #8b949e;
    border: 1px solid #30363d; border-radius: 3px;
    padding: 2px 10px; font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 700;
}
.sm-online  { color: #00ff88; font-weight: 700; }
.sm-offline { color: #ff4444; font-weight: 700; }
.sm-quote {
    background: #0a0e14; border-left: 3px solid #00ff88;
    padding: 10px 14px; border-radius: 0 4px 4px 0;
    color: #8b949e; font-style: italic; font-size: 14px;
    margin: 8px 0;
}
.sm-model-row {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; border-bottom: 1px solid #1c2128;
}
.sm-active-badge {
    background: #0d2b1a; color: #00ff88; border: 1px solid #00ff88;
    border-radius: 3px; padding: 1px 6px; font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
}

/* ── Ticker tape animation ─────────────────────────────────────── */
@keyframes ticker {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.sm-ticker {
    overflow: hidden; background: #0a0e14;
    border: 1px solid #1c2128; border-radius: 4px;
    padding: 6px 0; white-space: nowrap;
}
.sm-ticker-inner {
    display: inline-block;
    animation: ticker 25s linear infinite;
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; letter-spacing: 1px;
}

/* ── Pulse animation (AI thinking) ────────────────────────────── */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.2; }
}
.sm-pulse {
    animation: pulse 1.5s infinite;
    color: #00ff88; font-family: 'IBM Plex Mono', monospace;
}
.sm-scan-line {
    height: 2px; background: linear-gradient(90deg, transparent, #00ff88, transparent);
    animation: scan 2s linear infinite;
}
@keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Finance-Zitate & Ticker-Tape
# ─────────────────────────────────────────────────────────────────────────────
QUOTES = [
    "Sei gierig, wenn andere ängstlich sind. – Warren Buffett",
    "Die Börse ist ein Instrument um Geld von Ungeduldigen zu Geduldigen zu transferieren. – W. Buffett",
    "Kurzfristig ist die Börse eine Abstimmungsmaschine, langfristig eine Waage. – Benjamin Graham",
    "Der Markt kann länger irrational bleiben als du solvent. – J. M. Keynes",
    "Kaufe, wenn alle verkaufen. Verkaufe, wenn alle kaufen. – J. Paul Getty",
    "Risiko kommt daher, dass man nicht weiß, was man tut. – Warren Buffett",
    "Der beste Zeitpunkt zu investieren war gestern. Der zweitbeste ist heute.",
    "Diversifikation ist Schutz gegen Unwissenheit. – Warren Buffett",
    "In der Investition ist das, was komfortabel ist, selten profitabel. – Robert Arnott",
    "Zeit im Markt schlägt das Timing des Marktes.",
    "Der Markt ist ein Ort, wo Wertpapiere von Aktiven zu Geduldigen wandern. – Nicolas Darvas",
    "Vier Worte, die Investoren viel Geld gekostet haben: Diesmal ist es anders. – Sir John Templeton",
]

_TICKER_WORDS = (
    "KAUFEN • HALTEN • VERKAUFEN • RSI • MACD • BOLLINGER • "
    "KI ANALYSIERT • MUSTER ERKANNT • SIGNAL • TREND • VOLUMEN • "
    "SUPPORT • RESISTANCE • MOMENTUM • DIVERGENZ • BREAKOUT • "
)


def ticker_html() -> str:
    tape = _TICKER_WORDS * 5
    return f'<div class="sm-ticker"><span class="sm-ticker-inner">{tape}</span></div>'


def quote_html(quote: str) -> str:
    # LLM-/API-Text darf nie roh ins HTML (Stored XSS über persistierte Insights)
    return f'<div class="sm-quote">"{html.escape(quote)}"</div>'


def signal_badge_html(signal: str) -> str:
    mapping = {
        "UP": "sm-badge-up",
        "KAUFEN": "sm-badge-up",
        "BUY": "sm-badge-up",
        "DOWN": "sm-badge-down",
        "VERKAUFEN": "sm-badge-down",
        "SELL": "sm-badge-down",
        "NEUTRAL": "sm-badge-neutral",
        "HALTEN": "sm-badge-neutral",
        "HOLD": "sm-badge-neutral",
    }
    cls = mapping.get(signal.upper(), "sm-badge-neutral")
    return f'<span class="{cls}">{html.escape(signal)}</span>'


def section(label: str) -> None:
    st.markdown(f'<div class="sm-header">{label}</div>', unsafe_allow_html=True)
