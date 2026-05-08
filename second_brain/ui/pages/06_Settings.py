"""Settings page: vault config, Ollama, reindex, backup, and DB management."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from ui.app_state import (
    get_vault_manager,
    get_vault_stats,
    init_session_state,
    invalidate_data_caches,
    refresh_vault_stats,
)

init_session_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    st.markdown(f"### {title}")


def _ollama_test(url: str) -> tuple[bool, list[str]]:
    try:
        from ai.ollama_client import OllamaClient
        client = OllamaClient(base_url=url)
        ok = client.is_available()
        models = client.list_models() if ok else []
        return ok, models
    except Exception:
        return False, []


def _reindex_vault(vault_path: Path) -> None:
    progress = st.progress(0, text="Starte Reindexierung…")
    status = st.empty()
    try:
        status.info("Scanne Vault-Dateien…")
        progress.progress(10)

        from core.database import full_sync
        full_sync(vault_path)
        progress.progress(40, text="Datenbank synchronisiert…")

        status.info("Indiziere Embeddings (max 50 pro Batch)…")
        from ai.embedder import NoteEmbedder
        from core.vault_manager import VaultManager

        vm_local = VaultManager(vault_path)
        notes_local = vm_local.get_all_notes()
        total = max(len(notes_local), 1)

        emb = NoteEmbedder()
        emb.reindex_all.__func__  # ensure method exists
        emb._chroma.delete_collection(emb._collection_name)
        emb._col = emb._chroma.get_or_create_collection(
            name=emb._collection_name, metadata={"hnsw:space": "cosine"}
        )

        def _prog(done: int, tot: int) -> None:
            pct = 40 + int(50 * done / tot)
            progress.progress(pct, text=f"Embedding {done}/{tot}…")

        emb.embed_all_notes(notes_local, progress_callback=_prog)

        invalidate_data_caches()
        refresh_vault_stats()
        progress.progress(100, text="Fertig!")
        status.success(f"Vault neu indiziert – {len(notes_local)} Notizen.")
        st.toast("Vault neu indiziert!", icon="✅")
    except Exception as exc:
        progress.empty()
        status.error(f"Fehler beim Reindexieren: {exc}")


def _backup_vault(vault_path: Path) -> bytes | None:
    import io, zipfile
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for md_file in sorted(vault_path.glob("**/*.md")):
                zf.write(md_file, md_file.relative_to(vault_path.parent))
        buf.seek(0)
        return buf.read()
    except Exception as exc:
        st.error(f"Backup-Fehler: {exc}")
        return None


def _reset_db() -> None:
    try:
        from core.database import init_db
        from core.config import engine
        from core.database import Base
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        refresh_vault_stats()
        st.success("Datenbank wurde zurückgesetzt.")
    except Exception as exc:
        st.error(f"Reset-Fehler: {exc}")


def _chroma_count() -> int:
    try:
        from ai.embedder import NoteEmbedder
        emb = NoteEmbedder()
        return emb.collection_count()
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.markdown("<h1>⚙️ Einstellungen</h1>", unsafe_allow_html=True)
st.divider()

# ── Vault ────────────────────────────────────────────────────────────────────
_section("📁 Vault-Pfad")

from core.config import VAULT_DIR
from core.config_store import get as cfg_get, set as cfg_set

_saved_vault = cfg_get("vault_dir", str(VAULT_DIR))
vault_input = st.text_input(
    "Vault-Verzeichnis",
    value=_saved_vault,
    label_visibility="collapsed",
    key="settings_vault_path",
)
vcol1, vcol2, vcol3, _ = st.columns([1, 1, 1, 2])
with vcol1:
    if st.button("✅ Prüfen", use_container_width=True):
        vp = Path(vault_input)
        if vp.exists() and vp.is_dir():
            md_count = len(list(vp.glob("**/*.md")))
            st.success(f"Verzeichnis gefunden – {md_count} Markdown-Dateien.")
        else:
            st.error("Verzeichnis nicht gefunden.")
with vcol2:
    if st.button("💾 Speichern", use_container_width=True):
        vp = Path(vault_input)
        if vp.exists() and vp.is_dir():
            cfg_set("vault_dir", str(vp))
            st.toast("Vault-Pfad gespeichert! Neustart erforderlich.", icon="💾")
        else:
            st.error("Verzeichnis nicht gefunden – Pfad nicht gespeichert.")
with vcol3:
    if st.button("📂 Öffnen", use_container_width=True):
        import subprocess, platform
        p = Path(vault_input)
        if platform.system() == "Darwin":
            subprocess.Popen(["open", str(p)])
        elif platform.system() == "Linux":
            subprocess.Popen(["xdg-open", str(p)])
        else:
            subprocess.Popen(["explorer", str(p)])

st.divider()

# ── Ollama ───────────────────────────────────────────────────────────────────
_section("🤖 Ollama-Verbindung")

from core.config import OLLAMA_URL, EMBED_MODEL, CHAT_MODEL
ollama_url = st.text_input("Ollama URL", value=OLLAMA_URL, key="settings_ollama_url")

ocol1, ocol2 = st.columns([1, 3])
with ocol1:
    test_clicked = st.button("🔌 Verbindung testen", use_container_width=True)

if test_clicked:
    with st.spinner("Teste Verbindung…"):
        ok, models = _ollama_test(ollama_url)
    if ok:
        st.success(f"Ollama erreichbar — {len(models)} Modell(e) gefunden.")
        if models:
            embed_model = st.selectbox("Embedding-Modell", models, index=models.index(EMBED_MODEL) if EMBED_MODEL in models else 0)
            chat_model = st.selectbox("Chat-Modell", models, index=models.index(CHAT_MODEL) if CHAT_MODEL in models else 0)
            st.info("Modell-Auswahl wird beim nächsten Start übernommen (config.py bearbeiten).")
    else:
        st.error("Ollama nicht erreichbar. Starte mit: `ollama serve`")
else:
    with st.expander("Verfügbare Modelle"):
        ok, models = _ollama_test(ollama_url)
        if ok and models:
            for m in models:
                status = "✅" if m in (EMBED_MODEL, CHAT_MODEL) else "·"
                st.markdown(f"`{status}` `{m}`")
        elif not ok:
            st.caption("Ollama offline.")

st.divider()

# ── Reindex ───────────────────────────────────────────────────────────────────
_section("🔄 Vault neu indizieren")
st.markdown(
    "<p style='color:#a6adc8;font-size:13px;'>Aktualisiert die SQLite-Datenbank "
    "und ChromaDB-Embeddings für alle Notizen im Vault.</p>",
    unsafe_allow_html=True,
)
if st.button("🔄 Jetzt neu indizieren", type="primary", key="settings_reindex"):
    _reindex_vault(Path(vault_input))

st.divider()

# ── Backup ────────────────────────────────────────────────────────────────────
_section("💾 Vault-Backup")
st.markdown(
    "<p style='color:#a6adc8;font-size:13px;'>Erstellt ein ZIP-Archiv "
    "aller Markdown-Dateien im Vault.</p>",
    unsafe_allow_html=True,
)
if st.button("📦 Backup erstellen", key="settings_backup"):
    with st.spinner("Erstelle Backup…"):
        data = _backup_vault(Path(vault_input))
    if data:
        from datetime import datetime
        fname = f"vault_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        st.download_button(
            label=f"⬇️ {fname} herunterladen",
            data=data,
            file_name=fname,
            mime="application/zip",
        )

st.divider()

# ── DB Reset ─────────────────────────────────────────────────────────────────
_section("🗑️ Datenbank zurücksetzen")
st.markdown(
    "<p style='color:#f38ba8;font-size:13px;'>⚠️ Löscht alle Datenbankeinträge "
    "(Notizen bleiben als Markdown-Dateien erhalten).</p>",
    unsafe_allow_html=True,
)

if st.button("🗑 Datenbank zurücksetzen", key="settings_db_reset_btn"):
    st.session_state["_confirm_db_reset"] = True

if st.session_state.get("_confirm_db_reset"):
    st.warning("Wirklich alle Datenbankeinträge löschen?")
    yes_col, no_col, _ = st.columns([1, 1, 4])
    with yes_col:
        if st.button("✅ Ja, zurücksetzen", type="primary", key="settings_db_reset_yes"):
            _reset_db()
            st.session_state["_confirm_db_reset"] = False
    with no_col:
        if st.button("❌ Abbrechen", key="settings_db_reset_no"):
            st.session_state["_confirm_db_reset"] = False
            st.rerun()

st.divider()

# ── App Info ─────────────────────────────────────────────────────────────────
_section("ℹ️ App-Info")

from core.config import APP_NAME, VERSION
try:
    stats = get_vault_stats()
except Exception:
    stats = {}

chroma_count = _chroma_count()

info_col1, info_col2 = st.columns(2)
with info_col1:
    st.markdown(
        f"**App:** {APP_NAME}  \n"
        f"**Version:** `{VERSION}`  \n"
        f"**Vault:** `{vault_input}`  \n"
    )
with info_col2:
    st.markdown(
        f"**Notizen:** {stats.get('total_notes', '–')}  \n"
        f"**Tags:** {stats.get('total_tags', '–')}  \n"
        f"**ChromaDB Dokumente:** {chroma_count if chroma_count >= 0 else '–'}  \n"
    )

try:
    import streamlit as _st
    import chromadb as _chroma
    import sqlalchemy as _sa
    import pyvis as _pyvis
    st.markdown(
        f"**Streamlit:** `{_st.__version__}`  \n"
        f"**ChromaDB:** `{_chroma.__version__}`  \n"
        f"**SQLAlchemy:** `{_sa.__version__}`  \n"
        f"**pyvis:** `{_pyvis.__version__}`"
    )
except Exception:
    pass

if not st.session_state.get("_confirm_db_reset"):
    st.session_state["_confirm_db_reset"] = False
