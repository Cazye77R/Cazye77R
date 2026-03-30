"""Streamlit UI for the lightweight text search tool."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import List

import streamlit as st

try:
    from .loader import Chunk, load_file
    from .searcher import SearchIndex, SearchMode, SearchResult, build_search_index, load_index, save_index
    from .chat import ChatConfig, answer_question, DEFAULT_SMALL_MODEL
except ImportError:
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from text_search.loader import Chunk, load_file  # type: ignore[no-redef]
    from text_search.searcher import SearchIndex, SearchMode, SearchResult, build_search_index, load_index, save_index  # type: ignore[no-redef]
    from text_search.chat import ChatConfig, answer_question, DEFAULT_SMALL_MODEL  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Speed presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "⚡ Schnell":    {"mode": "keyword",  "chunk_size": 500, "overlap": 0,  "top_k": 5,  "batch_size": 64},
    "⚖ Ausgewogen": {"mode": "hybrid",   "chunk_size": 300, "overlap": 50, "top_k": 10, "batch_size": 64},
    "🎯 Präzise":   {"mode": "semantic", "chunk_size": 150, "overlap": 50, "top_k": 15, "batch_size": 128},
}

MODEL_INFO: dict[str, dict] = {
    "all-MiniLM-L6-v2":  {"size": "~27 MB",  "dim": 384, "speed": "schnell", "score": "58.9"},
    "all-mpnet-base-v2":  {"size": "~420 MB", "dim": 768, "speed": "langsam", "score": "63.3"},
}

# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Embedding-Modell wird geladen...")
def _cached_model(model_name: str, offline: bool) -> None:
    import os
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
    if offline:
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    return SentenceTransformer(model_name)


@st.cache_data(show_spinner="Index wird aufgebaut...")
def _cached_index(
    file_bytes_map: dict[str, bytes],
    semantic: bool,
    effective_model: str,
    chunk_size: int,
    overlap: int,
    batch_size: int,
    offline: bool,
) -> SearchIndex:
    chunks: List[Chunk] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for filename, data in file_bytes_map.items():
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(data)
            chunks.extend(load_file(tmp_path, chunk_size=chunk_size, overlap=overlap))
    return build_search_index(
        chunks,
        semantic=semantic,
        model_name=effective_model,
        batch_size=batch_size,
        offline=offline,
    )


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

_DARK_CSS = """
<style>
.stApp {
    background: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.12), transparent 25%),
                radial-gradient(circle at 80% 0%, rgba(168, 85, 247, 0.12), transparent 25%),
                #0b1220;
    color: #e5e7eb;
}
.block-container { padding-top: 1.5rem; }
.stDataFrame, .stMetric {
    background-color: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    padding: 8px;
}
.score-badge {
    display: inline-block;
    background: rgba(34,211,238,0.2);
    color: #22d3ee;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.8em;
    margin-right: 8px;
}
</style>
"""


def _build_snippet(text: str, query: str, context_words: int = 30) -> str:
    words = text.split()
    query_tokens = re.sub(r"[^\w\s]", " ", query).lower().split()
    best_pos = 0
    for i, w in enumerate(words):
        if w.lower() in query_tokens:
            best_pos = i
            break
    start = max(0, best_pos - context_words)
    end = min(len(words), best_pos + context_words)
    snippet = " ".join(words[start:end])
    if start > 0:
        snippet = "..." + snippet
    if end < len(words):
        snippet = snippet + "..."
    return _highlight_query(snippet, query)


def _highlight_query(text: str, query: str) -> str:
    for term in re.sub(r"[^\w\s]", " ", query).lower().split():
        text = re.sub(rf"(?i)({re.escape(term)})", r"**\1**", text)
    return text


def _get_neighbors(all_chunks: list[Chunk], chunk: Chunk, n: int = 1) -> list[Chunk]:
    same = sorted(
        [c for c in all_chunks if c.source == chunk.source],
        key=lambda c: c.chunk_id,
    )
    idx = next((i for i, c in enumerate(same) if c.chunk_id == chunk.chunk_id), None)
    if idx is None:
        return []
    return same[max(0, idx - n) : idx] + same[idx + 1 : idx + 1 + n]


def _render_result(
    result: SearchResult,
    rank: int,
    query: str,
    all_chunks: list[Chunk],
    file_bytes_map: dict[str, bytes],
) -> None:
    score_pct = f"{result.score * 100:.1f}%" if result.score <= 1.0 else f"{result.score:.2f}"
    loc = ""
    if result.chunk.page is not None:
        loc = f"  ·  Seite {result.chunk.page}"
    elif result.chunk.line_start is not None:
        loc = f"  ·  Zeile {result.chunk.line_start}"
    header = f"#{rank}  {result.chunk.source}{loc}"

    with st.expander(header, expanded=rank <= 3):
        top_cols = st.columns([2, 2, 3])
        with top_cols[0]:
            st.markdown(
                f'<span class="score-badge">Score {score_pct}</span>',
                unsafe_allow_html=True,
            )
        with top_cols[1]:
            if result.chunk.source in file_bytes_map:
                st.download_button(
                    label="⬇ Quelldatei",
                    data=file_bytes_map[result.chunk.source],
                    file_name=result.chunk.source,
                    key=f"dl_{result.chunk.chunk_id}",
                )
        with top_cols[2]:
            show_full = st.checkbox("Volltext anzeigen", key=f"full_{result.chunk.chunk_id}")

        st.divider()

        if show_full:
            neighbors = _get_neighbors(all_chunks, result.chunk)
            for c in [x for x in neighbors if x.chunk_id < result.chunk.chunk_id]:
                st.caption(f"← Vorheriger Chunk (#{c.chunk_id})")
                st.text(c.text)
                st.divider()
            st.caption(f"Treffer-Chunk #{result.chunk.chunk_id}")
            st.markdown(_highlight_query(result.chunk.text, query))
            for c in [x for x in neighbors if x.chunk_id > result.chunk.chunk_id]:
                st.divider()
                st.caption(f"→ Nächster Chunk (#{c.chunk_id})")
                st.text(c.text)
        else:
            st.markdown(_build_snippet(result.chunk.text, query))


# ---------------------------------------------------------------------------
# Ollama setup wizard
# ---------------------------------------------------------------------------

def _run_ollama_pull(model: str, host: str) -> None:
    import subprocess, shutil
    if not shutil.which("ollama"):
        st.error("ollama-Binary nicht gefunden. Bitte zuerst Ollama installieren.")
        return
    with st.status(f"Lade {model} herunter…", expanded=True) as pull_status:
        proc = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output_area = st.empty()
        lines: list = []
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip())
            output_area.code("\n".join(lines[-15:]))
        proc.wait()
        if proc.returncode == 0:
            pull_status.update(label=f"✅ {model} bereit!", state="complete")
            st.session_state["ollama_model_ready"] = model
            st.rerun()
        else:
            pull_status.update(label="Fehler beim Herunterladen", state="error")


def _show_model_picker(config: "ChatConfig") -> None:  # type: ignore[name-defined]
    try:
        from .chat import MODEL_CATALOG, DEFAULT_SMALL_MODEL
    except ImportError:
        from text_search.chat import MODEL_CATALOG, DEFAULT_SMALL_MODEL  # type: ignore[no-redef]

    st.markdown("### Modell herunterladen")
    model_options = list(MODEL_CATALOG.keys())
    default_idx = model_options.index(DEFAULT_SMALL_MODEL) if DEFAULT_SMALL_MODEL in model_options else 0
    sel = st.selectbox(
        "Modell wählen",
        model_options,
        index=default_idx,
        format_func=lambda m: MODEL_CATALOG[m]["label"],
        key="wizard_model_select",
    )
    info = MODEL_CATALOG[sel]
    st.caption(f"Speicherbedarf: ca. **{info['size_gb']} GB** — einmalig herunterladen, danach 100% lokal")
    if st.button(f"⬇ {sel} herunterladen", type="primary", key="wizard_pull_btn"):
        _run_ollama_pull(sel, config.ollama_host)


def _ollama_setup_wizard(config: "ChatConfig") -> bool:  # type: ignore[name-defined]
    """Show Ollama setup UI. Returns True if Ollama + model are ready."""
    import platform
    try:
        from .chat import check_ollama_status
    except ImportError:
        from text_search.chat import check_ollama_status  # type: ignore[no-redef]

    status = check_ollama_status(config.ollama_host, config.model)
    if status.model_ready:
        return True

    st.info("**Ollama-Einrichtung erforderlich**", icon="🛠")

    if not status.installed:
        os_name = platform.system()
        st.markdown("#### Schritt 1 — Ollama installieren")
        if os_name == "Windows":
            st.markdown("Lade den Installer herunter und starte ihn:")
            st.code("https://ollama.com/download/windows", language="text")
        elif os_name == "Darwin":
            st.markdown("Lade die macOS App herunter:")
            st.code("https://ollama.com/download/mac", language="text")
        else:
            st.markdown("Linux — im Terminal ausführen:")
            st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")
        st.markdown("#### Schritt 2 — Ollama starten")
        st.code("ollama serve", language="bash")
        st.markdown("#### Schritt 3 — Modell laden")
        _show_model_picker(config)
        return False

    if not status.running:
        st.warning("Ollama ist installiert, aber nicht gestartet.")
        st.markdown("**Terminal öffnen und eingeben:**")
        st.code("ollama serve", language="bash")
        st.markdown("Danach diese Seite neu laden (F5).")
        return False

    # Ollama running, model missing
    st.success("Ollama läuft", icon="✅")
    if status.available_models:
        st.caption("Bereits installierte Modelle: " + ", ".join(status.available_models))
    _show_model_picker(config)
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Text Search", page_icon="🔍", layout="wide")
    st.markdown(_DARK_CSS, unsafe_allow_html=True)
    st.title("🔍 Lightweight Text Search")

    # ── Sidebar: Presets & Settings ─────────────────────────────────────────
    st.sidebar.header("Einstellungen")
    preset_name = st.sidebar.radio("Voreinstellung", list(PRESETS.keys()), index=1)
    preset = PRESETS[preset_name]
    st.sidebar.markdown("---")

    _all_modes = ["hybrid", "keyword", "semantic", "chat"]
    _preset_mode = preset["mode"] if preset["mode"] in _all_modes else "hybrid"
    mode: str = st.sidebar.radio(  # type: ignore[assignment]
        "Suchmodus",
        options=_all_modes,
        index=_all_modes.index(_preset_mode),
        format_func=lambda x: {
            "hybrid": "Hybrid",
            "keyword": "Keyword (BM25)",
            "semantic": "Semantik",
            "chat": "💬 Chat",
        }[x],
        captions=[
            "Kombination aus beidem, beste Ergebnisse",
            "Exakte Wortsuche, sehr schnell, kein KI-Modell nötig",
            "Bedeutungssuche, findet sinnverwandte Treffer, benötigt KI-Modell",
            "Stellt Fragen in natürlicher Sprache, KI antwortet aus deinen Dokumenten",
        ],
    )
    top_k = preset["top_k"]
    semantic_weight = 0.5
    if mode != "chat":
        top_k = st.sidebar.slider("Anzahl Ergebnisse", 1, 20, value=preset["top_k"])
        if mode == "hybrid":
            semantic_weight = st.sidebar.slider(
                "Semantik-Gewicht", 0.0, 1.0, value=0.5, step=0.05
            )

    with st.sidebar.expander("Erweiterte Einstellungen", expanded=False):
        chunk_size = st.slider("Chunk-Größe (Wörter)", 50, 800,
                               value=preset["chunk_size"], step=50)
        overlap    = st.slider("Überlappung (Wörter)", 0, 200,
                               value=preset["overlap"], step=10)
        batch_size = st.select_slider(
            "Embedding Batch-Size",
            options=[16, 32, 64, 128, 256],
            value=preset["batch_size"],
        )

    use_semantic = mode in ("semantic", "hybrid")
    model_name = "all-MiniLM-L6-v2"
    offline = True
    effective_model = model_name

    # ── Chat-Einstellungen (nur wenn Chat-Modus aktiv) ───────────────────────
    chat_config = ChatConfig()
    if mode == "chat":
        st.sidebar.markdown("---")
        st.sidebar.subheader("Chat-Einstellungen")

        _provider_labels = ["Ollama (lokal)", "Claude API", "OpenAI API"]
        _provider_keys   = ["ollama", "claude", "openai"]
        if "chat_provider" not in st.session_state:
            st.session_state["chat_provider"] = "Ollama (lokal)"

        provider_label = st.sidebar.selectbox(
            "Provider",
            _provider_labels,
            index=_provider_labels.index(st.session_state["chat_provider"]),
            key="chat_provider_select",
        )
        provider = _provider_keys[_provider_labels.index(provider_label)]

        _default_models = {"ollama": DEFAULT_SMALL_MODEL, "claude": "claude-3-5-haiku-20241022", "openai": "gpt-4o-mini"}
        chat_model = st.sidebar.text_input(
            "Modell",
            value=_default_models[provider],
            key=f"chat_model_{provider}",
        )
        api_key = ""
        if provider in ("claude", "openai"):
            api_key = st.sidebar.text_input(
                "API-Key",
                type="password",
                key=f"chat_apikey_{provider}",
            )
        ollama_host = "http://localhost:11434"
        if provider == "ollama":
            ollama_host = st.sidebar.text_input(
                "Ollama Host",
                value="http://localhost:11434",
                key="chat_ollama_host",
            )
        context_chunks = st.sidebar.slider(
            "Kontext-Chunks", min_value=1, max_value=10, value=3,
            help="Anzahl der Dokument-Ausschnitte, die an die KI übergeben werden. Weniger = schneller.",
        )
        if st.sidebar.button("Lokal zurücksetzen", key="chat_reset"):
            st.session_state["chat_provider"] = "Ollama (lokal)"
            st.rerun()

        chat_config = ChatConfig(
            provider=provider,
            model=chat_model,
            api_key=api_key,
            ollama_host=ollama_host,
            context_chunks=context_chunks,
        )

    if use_semantic:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Embedding-Modell")
        model_name = st.sidebar.selectbox("Modell", options=list(MODEL_INFO.keys()), index=0)
        local_model_path = st.sidebar.text_input(
            "Lokaler Modellpfad (optional)",
            placeholder="/pfad/zum/modell",
        )
        offline = st.sidebar.checkbox(
            "Offline-Modus",
            value=True,
            help="Setzt TRANSFORMERS_OFFLINE=1. Deaktivieren für den ersten Download.",
        )
        effective_model = local_model_path.strip() or model_name
        info = MODEL_INFO.get(model_name, {})
        network_line = "🔒 Vollständig lokal" if offline else "🌐 Einmalig von HuggingFace · danach 100% lokal"
        if info:
            st.sidebar.info(
                f"**{effective_model}**  \n"
                f"Größe: {info['size']} · Dim: {info['dim']}  \n"
                f"Geschwindigkeit: {info['speed']} · MTEB: {info['score']}  \n"
                f"{network_line}"
            )
        try:
            _cached_model(effective_model, offline)
        except Exception:
            pass
    else:
        st.sidebar.info("⚡ Keyword-Modus: kein Modell nötig, 100% lokal.")

    # ── Restore index from session_state (instant cache hit) ────────────────
    search_index: SearchIndex | None = None
    if "index_params" in st.session_state:
        try:
            search_index = _cached_index(**st.session_state["index_params"])
        except Exception:
            del st.session_state["index_params"]

    # ── Restore index from pkl upload (sidebar) ──────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Index-Cache")
    cached_index_upload = st.sidebar.file_uploader(
        "Gespeicherten Index laden (.pkl)", type=["pkl"]
    )
    if cached_index_upload is not None and search_index is None:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
                tmp.write(cached_index_upload.getbuffer())
            search_index = load_index(Path(tmp.name))
            st.sidebar.success(f"Index geladen ({len(search_index.keyword_index.chunks)} Chunks)")
        except Exception as exc:
            st.sidebar.error(f"Fehler: {exc}")

    # Index download
    if search_index is not None:
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
            save_index(search_index, Path(tmp.name))
            idx_bytes = Path(tmp.name).read_bytes()
        st.sidebar.download_button(
            "Index herunterladen (.pkl)",
            data=idx_bytes,
            file_name="text_search_index.pkl",
            mime="application/octet-stream",
        )

    # ── SEARCH MODE ──────────────────────────────────────────────────────────
    if search_index is not None:
        file_bytes_map: dict[str, bytes] = st.session_state.get("file_bytes_map", {})
        n_chunks = len(search_index.keyword_index.chunks)
        n_files  = len({c.source for c in search_index.keyword_index.chunks})

        # Search form — Enter key works
        _placeholder = "Stelle eine Frage zu deinen Dokumenten…" if mode == "chat" else "Begriff oder Frage eingeben und Enter drücken…"
        _btn_label   = "Fragen" if mode == "chat" else "Suchen"
        with st.form("search_form"):
            query = st.text_input(
                "Suchanfrage",
                placeholder=_placeholder,
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(_btn_label, type="primary", use_container_width=True)

        st.caption(f"Index aktiv: **{n_chunks} Chunks** aus **{n_files} Datei(en)**")

        # Reset button
        if st.button("Neuen Index aufbauen", type="secondary"):
            del st.session_state["index_params"]
            if "file_bytes_map" in st.session_state:
                del st.session_state["file_bytes_map"]
            st.rerun()

        # Ollama setup wizard — shown whenever chat mode is active and Ollama not ready
        _ollama_ready = True
        if mode == "chat" and chat_config.provider == "ollama":
            _ollama_ready = _ollama_setup_wizard(chat_config)

        # Results
        if submitted and query.strip():
            all_chunks = search_index.keyword_index.chunks

            if mode == "chat":
                # Block submission if Ollama wizard is not yet done
                if chat_config.provider == "ollama" and not _ollama_ready:
                    st.stop()
                # API-Key validation for cloud providers
                if chat_config.provider in ("claude", "openai") and not chat_config.api_key.strip():
                    st.warning(
                        f"Bitte einen API-Key für {chat_config.provider.capitalize()} eingeben."
                    )
                    st.stop()
                try:
                    stream_gen, sources = answer_question(query, search_index, chat_config)
                    st.markdown("**Antwort:**")
                    st.write_stream(stream_gen)
                    if sources:
                        with st.expander("📎 Quellen"):
                            for rank, r in enumerate(sources, 1):
                                _render_result(r, rank, query, all_chunks, file_bytes_map)
                except ConnectionError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Fehler: {exc}")
            else:
                try:
                    from .searcher import search as do_search
                except ImportError:
                    from text_search.searcher import search as do_search  # type: ignore[no-redef]

                results = do_search(
                    search_index,
                    query=query,
                    mode=mode,
                    top_k=top_k,
                    semantic_weight=semantic_weight,
                    offline=offline,
                )

                if results:
                    all_sources = sorted({r.chunk.source for r in results})
                    if len(all_sources) > 1:
                        st.sidebar.markdown("---")
                        st.sidebar.subheader("Ergebnisse filtern")
                        selected_sources = st.sidebar.multiselect(
                            "Nach Quelle", all_sources, default=all_sources, key="source_filter"
                        )
                        results = [r for r in results if r.chunk.source in selected_sources]

                    st.markdown(f"**{len(results)} Ergebnis(se)** für *{query}*")
                    for rank, result in enumerate(results, start=1):
                        _render_result(result, rank, query, all_chunks, file_bytes_map)
                else:
                    st.warning("Keine Treffer gefunden.")

    # ── SETUP MODE ───────────────────────────────────────────────────────────
    else:
        st.subheader("1. Dateien hochladen")
        uploaded_files = st.file_uploader(
            "Wähle eine oder mehrere Dateien",
            type=["txt", "md", "csv", "pdf"],
            accept_multiple_files=True,
        )

        if uploaded_files:
            file_bytes_map = {f.name: f.getvalue() for f in uploaded_files}
            index_params = dict(
                file_bytes_map=file_bytes_map,
                semantic=use_semantic,
                effective_model=effective_model,
                chunk_size=chunk_size,
                overlap=overlap,
                batch_size=batch_size,
                offline=offline,
            )
            st.subheader("2. Index aufbauen")
            preset_hint = f"Preset: **{preset_name}** · Chunk-Größe: {chunk_size} · Overlap: {overlap}"
            st.info(f"{len(uploaded_files)} Datei(en) bereit. {preset_hint}")

            if st.button("Index aufbauen", type="primary"):
                try:
                    _cached_index(**index_params)
                    # Persist params and file bytes for subsequent reruns
                    st.session_state["index_params"] = index_params
                    st.session_state["file_bytes_map"] = file_bytes_map
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fehler beim Indexieren: {exc}")
        else:
            st.info("Lade Textdateien hoch oder stelle einen gespeicherten Index wieder her.")


if __name__ == "__main__":
    main()
