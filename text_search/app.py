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
# Caching helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Embedding-Modell wird geladen...")
def _cached_model(model_name: str) -> None:
    """Pre-load the SentenceTransformer once per session."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
    return SentenceTransformer(model_name)


@st.cache_data(show_spinner="Index wird aufgebaut...")
def _cached_index(
    file_bytes_map: dict[str, bytes],
    semantic: bool,
    model_name: str,
) -> SearchIndex:
    """Build search index from a {filename: bytes} dict.
    Streamlit hashes the dict automatically — same uploads → instant cache hit.
    """
    chunks: List[Chunk] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for filename, data in file_bytes_map.items():
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(data)
            chunks.extend(load_file(tmp_path))

    return build_search_index(chunks, semantic=semantic, model_name=model_name)


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
.result-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
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
            # Download-Button direkt im Card (nur wenn Datei hochgeladen wurde)
            if result.chunk.source in file_bytes_map:
                st.download_button(
                    label=f"⬇ Quelldatei",
                    data=file_bytes_map[result.chunk.source],
                    file_name=result.chunk.source,
                    key=f"dl_{result.chunk.chunk_id}",
                )

        with top_cols[2]:
            show_full = st.checkbox(
                "Volltext anzeigen", key=f"full_{result.chunk.chunk_id}"
            )

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

    # --- Sidebar ---
    st.sidebar.header("Einstellungen")
    mode: SearchMode = st.sidebar.radio(  # type: ignore[assignment]
        "Suchmodus",
        options=["hybrid", "keyword", "semantic"],
        format_func=lambda x: {"hybrid": "Hybrid", "keyword": "Keyword (BM25)", "semantic": "Semantik"}[x],
    )
    top_k = st.sidebar.slider("Anzahl Ergebnisse", min_value=1, max_value=20, value=10)
    semantic_weight = 0.5
    if mode == "hybrid":
        semantic_weight = st.sidebar.slider(
            "Semantik-Gewicht", min_value=0.0, max_value=1.0, value=0.5, step=0.05
        )

    use_semantic = mode in ("semantic", "hybrid")
    model_name = "all-MiniLM-L6-v2"
    if use_semantic:
        model_name = st.sidebar.selectbox(
            "Embedding-Modell",
            options=["all-MiniLM-L6-v2", "all-mpnet-base-v2"],
            index=0,
        )
        _cached_model(model_name)

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

    # Build file_bytes_map for download buttons (empty if no upload)
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
        st.info(f"{len(uploaded_files)} Datei(en) bereit. Klicke auf den Button, um den Index zu erstellen.")

        if st.button("Index aufbauen", type="primary"):
            try:
                search_index = _cached_index(
                    file_bytes_map=file_bytes_map,
                    semantic=use_semantic,
                    model_name=model_name,
                )
                n_chunks = len(search_index.keyword_index.chunks)
                st.success(f"Index fertig — {n_chunks} Chunks aus {len(uploaded_files)} Datei(en)")
            except Exception as exc:
                st.error(f"Fehler beim Indexieren: {exc}")

        # Retrieve cached index without re-building
        if search_index is None:
            try:
                search_index = _cached_index.cache_data(  # type: ignore[attr-defined]
                    file_bytes_map=file_bytes_map,
                    semantic=use_semantic,
                    model_name=model_name,
                )
            except Exception:
                pass

    if search_index is not None:
        # Index download (sidebar)
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
