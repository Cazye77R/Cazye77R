"""Streamlit UI for the lightweight text search tool."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import List

import streamlit as st

from .loader import Chunk, load_file
from .searcher import SearchIndex, SearchMode, SearchResult, build_search_index, load_index, save_index

# ---------------------------------------------------------------------------
# Speed presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "⚡ Schnell":    {"mode": "keyword",  "chunk_size": 500, "overlap": 0,  "top_k": 5,  "batch_size": 64},
    "⚖ Ausgewogen": {"mode": "hybrid",   "chunk_size": 300, "overlap": 50, "top_k": 10, "batch_size": 64},
    "🎯 Präzise":   {"mode": "semantic", "chunk_size": 150, "overlap": 50, "top_k": 15, "batch_size": 128},
}

# Model metadata for the info box
MODEL_INFO: dict[str, dict] = {
    "all-MiniLM-L6-v2":  {"size": "~27 MB",  "dim": 384, "speed": "schnell", "score": "58.9"},
    "all-mpnet-base-v2":  {"size": "~420 MB", "dim": 768, "speed": "langsam", "score": "63.3"},
}

# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Embedding-Modell wird geladen...")
def _cached_model(model_name: str, offline: bool) -> None:
    """Pre-load the SentenceTransformer once per session."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
    import os
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
    """Build search index from a {filename: bytes} dict.
    All parameters flow into the cache key — changing any of them triggers a full rebuild.
    """
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
    """Return a ~60-word window centred around the first query term."""
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
    """Bold all query terms in text (case-insensitive)."""
    for term in re.sub(r"[^\w\s]", " ", query).lower().split():
        text = re.sub(rf"(?i)({re.escape(term)})", r"**\1**", text)
    return text


def _get_neighbors(all_chunks: list[Chunk], chunk: Chunk, n: int = 1) -> list[Chunk]:
    """Return up to n chunks before and after chunk within the same source."""
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

    # Seite/Zeile prominent im Header
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
            neighbors_before = [c for c in neighbors if c.chunk_id < result.chunk.chunk_id]
            neighbors_after = [c for c in neighbors if c.chunk_id > result.chunk.chunk_id]

            for c in neighbors_before:
                st.caption(f"← Vorheriger Chunk (Chunk #{c.chunk_id})")
                st.text(c.text)
                st.divider()

            st.caption(f"Treffer-Chunk #{result.chunk.chunk_id}")
            st.markdown(_highlight_query(result.chunk.text, query))

            for c in neighbors_after:
                st.divider()
                st.caption(f"→ Nächster Chunk (Chunk #{c.chunk_id})")
                st.text(c.text)
        else:
            st.markdown(_build_snippet(result.chunk.text, query))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Text Search", page_icon="🔍", layout="wide")
    st.markdown(_DARK_CSS, unsafe_allow_html=True)
    st.title("🔍 Lightweight Text Search")

    # --- Sidebar: Preset ---
    st.sidebar.header("Einstellungen")
    preset_name = st.sidebar.radio("Voreinstellung", list(PRESETS.keys()), index=1)
    preset = PRESETS[preset_name]
    st.sidebar.markdown("---")

    # --- Sidebar: Search mode (pre-filled from preset) ---
    mode: SearchMode = st.sidebar.radio(  # type: ignore[assignment]
        "Suchmodus",
        options=["hybrid", "keyword", "semantic"],
        index=["hybrid", "keyword", "semantic"].index(preset["mode"]),
        format_func=lambda x: {"hybrid": "Hybrid", "keyword": "Keyword (BM25)", "semantic": "Semantik"}[x],
    )
    top_k = st.sidebar.slider("Anzahl Ergebnisse", min_value=1, max_value=20,
                               value=preset["top_k"])
    semantic_weight = 0.5
    if mode == "hybrid":
        semantic_weight = st.sidebar.slider(
            "Semantik-Gewicht", min_value=0.0, max_value=1.0, value=0.5, step=0.05
        )

    # --- Sidebar: Advanced settings ---
    with st.sidebar.expander("Erweiterte Einstellungen", expanded=False):
        chunk_size = st.slider("Chunk-Größe (Wörter)", 50, 800,
                               value=preset["chunk_size"], step=50,
                               help="Größere Chunks = weniger Chunks = schnellerer Index. "
                                    "Kleinere Chunks = präzisere Treffer.")
        overlap = st.slider("Überlappung (Wörter)", 0, 200,
                            value=preset["overlap"], step=10,
                            help="Überlappung zwischen benachbarten Chunks. 0 = kein Overlap.")
        batch_size = st.select_slider(
            "Embedding Batch-Size",
            options=[16, 32, 64, 128, 256],
            value=preset["batch_size"],
            help="Größerer Batch = schnelleres Indexieren (benötigt mehr RAM/VRAM).",
        )

    # --- Sidebar: Model ---
    use_semantic = mode in ("semantic", "hybrid")
    model_name = "all-MiniLM-L6-v2"
    offline = False
    effective_model = model_name

    if use_semantic:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Embedding-Modell")
        model_name = st.sidebar.selectbox(
            "Modell",
            options=list(MODEL_INFO.keys()),
            index=0,
        )

        # Offline mode & local path
        local_model_path = st.sidebar.text_input(
            "Lokaler Modellpfad (optional)",
            placeholder="/pfad/zum/modell oder leer für Auto-Download",
            help="Lokalen Pfad angeben → kein Netzwerkzugriff nötig.",
        )
        offline = st.sidebar.checkbox(
            "Offline-Modus",
            value=bool(local_model_path.strip()),
            help="Setzt TRANSFORMERS_OFFLINE=1. Das Modell muss bereits lokal gecacht sein "
                 "(~/.cache/huggingface/) oder der Pfad oben muss angegeben sein.",
        )
        effective_model = local_model_path.strip() or model_name

        # Model info box
        info = MODEL_INFO.get(model_name, {})
        network_line = "🔒 Vollständig lokal (Offline-Modus)" if offline else "🌐 Einmalig von HuggingFace · danach 100% lokal"
        if info:
            st.sidebar.info(
                f"**{effective_model}**  \n"
                f"Größe: {info['size']} · Dim: {info['dim']}  \n"
                f"Geschwindigkeit: {info['speed']} · MTEB: {info['score']}  \n"
                f"{network_line}"
            )

        # Warm up model cache
        try:
            _cached_model(effective_model, offline)
        except Exception:
            pass
    else:
        st.sidebar.info("⚡ Keyword-Modus: kein Modell nötig, 100% lokal & offline.")

    # --- Sidebar: Index cache ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Index-Cache")
    cached_index_upload = st.sidebar.file_uploader(
        "Gespeicherten Index laden (.pkl)", type=["pkl"]
    )

    # --- File upload ---
    st.subheader("1. Dateien hochladen")
    uploaded_files = st.file_uploader(
        "Wähle eine oder mehrere Dateien",
        type=["txt", "md", "csv", "pdf"],
        accept_multiple_files=True,
    )

    file_bytes_map: dict[str, bytes] = {f.name: f.getvalue() for f in (uploaded_files or [])}
    search_index: SearchIndex | None = None

    # Restore from uploaded cache
    if cached_index_upload is not None:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
                tmp.write(cached_index_upload.getbuffer())
                tmp_path = Path(tmp.name)
            search_index = load_index(tmp_path)
            st.sidebar.success(f"Index geladen ({len(search_index.keyword_index.chunks)} Chunks)")
        except Exception as exc:
            st.sidebar.error(f"Fehler beim Laden: {exc}")

    if uploaded_files:
        st.subheader("2. Index aufbauen")
        preset_hint = f"Preset: **{preset_name}** · Chunk-Größe: {chunk_size} · Overlap: {overlap}"
        st.info(f"{len(uploaded_files)} Datei(en) bereit. {preset_hint}")

        if st.button("Index aufbauen", type="primary"):
            try:
                search_index = _cached_index(
                    file_bytes_map=file_bytes_map,
                    semantic=use_semantic,
                    effective_model=effective_model,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    batch_size=batch_size,
                    offline=offline,
                )
                n_chunks = len(search_index.keyword_index.chunks)
                st.success(f"Index fertig — {n_chunks} Chunks aus {len(uploaded_files)} Datei(en)")
            except Exception as exc:
                st.error(f"Fehler beim Indexieren: {exc}")

        if search_index is None:
            try:
                search_index = _cached_index.cache_data(  # type: ignore[attr-defined]
                    file_bytes_map=file_bytes_map,
                    semantic=use_semantic,
                    effective_model=effective_model,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    batch_size=batch_size,
                    offline=offline,
                )
            except Exception:
                pass

    if search_index is not None:
        # Index download
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
            save_index(search_index, Path(tmp.name))
            idx_bytes = Path(tmp.name).read_bytes()
        st.sidebar.download_button(
            "Index herunterladen (.pkl)",
            data=idx_bytes,
            file_name="text_search_index.pkl",
            mime="application/octet-stream",
        )

        # --- Search ---
        st.subheader("3. Suchen")
        query = st.text_input("Suchanfrage", placeholder="z.B. maschinelles Lernen")

        if query.strip():
            from .searcher import search as do_search

            results = do_search(
                search_index,
                query=query,
                mode=mode,
                top_k=top_k,
                semantic_weight=semantic_weight,
                offline=offline,
            )

            if results:
                # Quell-Filter (nur wenn mehrere Quellen vorhanden)
                all_sources = sorted({r.chunk.source for r in results})
                if len(all_sources) > 1:
                    st.sidebar.markdown("---")
                    st.sidebar.subheader("Ergebnisse filtern")
                    selected_sources = st.sidebar.multiselect(
                        "Nach Quelle",
                        options=all_sources,
                        default=all_sources,
                        key="source_filter",
                    )
                    results = [r for r in results if r.chunk.source in selected_sources]

                all_chunks = search_index.keyword_index.chunks
                st.markdown(f"**{len(results)} Ergebnis(se)** für *{query}*")
                for rank, result in enumerate(results, start=1):
                    _render_result(result, rank, query, all_chunks, file_bytes_map)
            else:
                st.warning("Keine Treffer gefunden.")
    elif not uploaded_files and cached_index_upload is None:
        st.info("Lade Textdateien hoch oder stelle einen gespeicherten Index wieder her, um zu beginnen.")


if __name__ == "__main__":
    main()
