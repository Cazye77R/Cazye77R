"""Shared cached resources and session-state helpers for all Streamlit pages."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st


# ---------------------------------------------------------------------------
# Heavy singletons – shared across all pages in the same server process
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_vault_manager():
    from core.vault_manager import VaultManager
    from core.config import VAULT_DIR
    from core.config_store import get as cfg_get
    vault_path = cfg_get("vault_dir", str(VAULT_DIR))
    return VaultManager(Path(vault_path))


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
# TTL-cached lightweight data queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_vault_stats_cached() -> dict:
    """Vault statistics, re-fetched at most every 5 minutes."""
    try:
        vm = get_vault_manager()
        return vm.get_stats()
    except Exception:
        return {"total_notes": 0, "total_words": 0, "total_tags": 0, "total_links": 0}


@st.cache_data(ttl=300, show_spinner=False)
def get_all_tags_cached() -> list[tuple[str, int]]:
    """Tag cloud data, re-fetched at most every 5 minutes."""
    try:
        from core.database import get_all_tags
        return get_all_tags()
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_ollama_status() -> bool:
    """True if Ollama is reachable. Cached for 60 seconds."""
    try:
        from ai.ollama_client import OllamaClient
        return OllamaClient().is_available()
    except Exception:
        return False


def render_ollama_warning() -> None:
    """Show a banner when Ollama is offline. Call near the top of pages that use AI."""
    if not get_ollama_status():
        st.warning(
            "⚠️ **Ollama nicht verfügbar** – KI-Funktionen (Chat, Embeddings, "
            "Tag-Vorschläge) sind deaktiviert.  \n"
            "Starte Ollama mit `ollama serve`, dann lade die Seite neu.",
            icon=None,
        )


def invalidate_data_caches() -> None:
    """Bust all TTL caches after vault mutations."""
    get_vault_stats_cached.clear()
    get_all_tags_cached.clear()


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "current_note": None,
    "search_results": [],
    "chat_history": [],
    "vault_stats": None,
    "note_edit_mode": False,
    "ai_tags": [],
    "ai_links": [],
    "ai_structure": "",
    "new_note_open": False,
    "_editor_dirty": False,
    "_editor_saved_content": "",
    "_confirm_delete": False,
    "_confirm_db_reset": False,
    "_graph_cache_key": "",
    "_graph_html": "",
}


def init_session_state() -> None:
    for key, val in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


def refresh_vault_stats() -> dict:
    """Bust caches and return fresh stats."""
    invalidate_data_caches()
    stats = get_vault_stats_cached()
    st.session_state["vault_stats"] = stats
    return stats


def get_vault_stats() -> dict:
    if st.session_state.get("vault_stats") is None:
        stats = get_vault_stats_cached()
        st.session_state["vault_stats"] = stats
        return stats
    return st.session_state["vault_stats"]
