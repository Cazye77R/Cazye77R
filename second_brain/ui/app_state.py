"""Shared cached resources and session-state helpers for all Streamlit pages."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure second_brain/ is on sys.path regardless of which page file triggers import
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st


# ---------------------------------------------------------------------------
# Cached resources (shared across all pages in the same server process)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_vault_manager():
    from core.vault_manager import VaultManager
    from core.config import VAULT_DIR
    return VaultManager(VAULT_DIR)


@st.cache_resource(show_spinner=False)
def get_rag_engine():
    try:
        from ai.rag_engine import RAGEngine
        return RAGEngine()
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def get_note_assistant():
    try:
        from ai.note_assistant import NoteAssistant
        return NoteAssistant()
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def get_smart_search():
    try:
        from plugins.smart_search import SmartSearch
        return SmartSearch()
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def get_link_suggester():
    try:
        from plugins.link_suggester import LinkSuggester
        return LinkSuggester()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "current_note": None,        # filename of active note
    "search_results": [],
    "chat_history": [],
    "vault_stats": None,
    "note_edit_mode": False,
    "ai_tags": [],
    "ai_links": [],
    "ai_structure": "",
    "new_note_open": False,
}


def init_session_state() -> None:
    for key, val in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


def refresh_vault_stats() -> dict:
    vm = get_vault_manager()
    stats = vm.get_stats()
    st.session_state["vault_stats"] = stats
    return stats


def get_vault_stats() -> dict:
    if st.session_state.get("vault_stats") is None:
        return refresh_vault_stats()
    return st.session_state["vault_stats"]
