"""
LocalTranscribe – Streamlit web application.

Entry point for the UI. Uploads audio, runs the transcription →
diarization → LLM pipeline, and lets users explore and export results.
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import torch

from config import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    OLLAMA_BASE_URL,
    SUPPORTED_FORMATS,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)
from diarizer import DiarizationError, SpeakerDiarizer
from llm_processor import LLMError, LLMProcessor
from transcriber import TranscriptionEngine, TranscriptionError
from utils import speaker_color, strip_remote_images

# st.set_page_config must be the very first Streamlit call in the script.
st.set_page_config(
    page_title="LocalTranscribe",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("pyannote").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]


_TASK_LABELS: dict[str, str] = {
    "Zusammenfassung":      "zusammenfassung",
    "Stichpunkte":          "stichpunkte",
    "Themen-Sortierung":    "themen",
    "Meeting-Protokoll":    "protokoll",
    "Formeller Bericht":    "bericht",
    "Maßnahmen & Aufgaben": "massnahmen",
    "Q&A extrahieren":      "faq",
    "Eigener Prompt":       "custom",
}

# One-liner shown as st.caption below the dropdown.
_TASK_DESCRIPTIONS: dict[str, str] = {
    "zusammenfassung": "Kurze Zusammenfassung der wichtigsten Punkte und Ergebnisse.",
    "stichpunkte":     "Maximal 15 Kernaussagen als kompakte Stichpunktliste.",
    "themen":          "Inhalte nach Themenbereichen sortiert und strukturiert.",
    "protokoll":       "Formelles Meeting-Protokoll mit Teilnehmern, Themen und Entscheidungen.",
    "bericht":         "Professioneller Bericht mit Zusammenfassung, Inhalten und Empfehlungen.",
    "massnahmen":      "Alle Aufgaben, Verantwortlichkeiten und Fristen als Liste.",
    "faq":             "Fragen und Antworten aus dem Gespräch als Q&A-Liste.",
    "custom":          "Eigener Prompt – du bestimmst das Ausgabeformat.",
}

# Used in download filenames: <stem>_<suffix>_<date>.txt
_TASK_FILE_SUFFIX: dict[str, str] = {
    "zusammenfassung": "zusammenfassung",
    "stichpunkte":     "stichpunkte",
    "themen":          "themen",
    "protokoll":       "protokoll",
    "bericht":         "bericht",
    "massnahmen":      "massnahmen",
    "faq":             "faq",
    "custom":          "analyse",
}

# Readable on both Streamlit light and dark themes.
_SPEAKER_COLORS = [
    "#4A90D9", "#E67E22", "#27AE60", "#8E44AD",
    "#E74C3C", "#16A085", "#F39C12", "#795548",
]

# st.file_uploader expects extensions without the leading dot.
_ACCEPT = [ext.lstrip(".") for ext in SUPPORTED_FORMATS]


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults: dict = {
        "segments": None,           # list[dict] – enriched transcript segments
        "transcription_meta": None, # dict – language, duration, filename
        "llm_output": None,         # str  – LLM analysis result
        "ollama_models": None,      # list[str] | None  (None = not yet fetched)
        "last_file_id": None,       # (name, size) tuple – detects new uploads
        "rec_audio_bytes": None,    # bytes | None – persisted browser recording
        "rec_audio_id": None,       # int | None  – len(bytes), detects new recordings
        "active_source": None,      # "upload" | "record" – which input to run
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_results() -> None:
    """
    Clear pipeline results only.

    Deliberately leaves the audio-source tracking keys (last_file_id,
    rec_audio_id) alone. Clearing another source's key here made the upload and
    recording blocks invalidate each other on every rerun, which wiped results
    in a loop. Which input is active is tracked by "active_source" instead.
    """
    st.session_state.update(
        segments=None,
        transcription_meta=None,
        llm_output=None,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar() -> dict:
    """Render all sidebar controls and return the current settings."""
    st.sidebar.header("Einstellungen")

    model_size: str = st.sidebar.selectbox(
        "Whisper-Modell",
        options=_WHISPER_MODELS,
        index=_WHISPER_MODELS.index(WHISPER_MODEL),
        help="Größere Modelle sind genauer, benötigen aber mehr VRAM und Zeit.",
    )  # type: ignore[assignment]

    _default_idx = list(LANGUAGES.keys()).index(DEFAULT_LANGUAGE)
    lang_label: str = st.sidebar.radio(
        "Sprache",
        options=list(LANGUAGES.keys()),
        index=_default_idx,
        horizontal=True,
        help="Explizite Sprachvorgabe verbessert die Erkennungsqualität gegenüber Auto-Detection.",
    )  # type: ignore[assignment]
    language = LANGUAGES[lang_label]

    st.sidebar.divider()

    use_diarization: bool = st.sidebar.checkbox(
        "Sprechererkennung aktivieren",
        value=True,
        help="Erkennt und beschriftet einzelne Sprecher im Transkript.",
    )

    num_speakers = 0
    hf_token = ""
    if use_diarization:
        num_speakers = int(st.sidebar.number_input(
            "Anzahl Sprecher (0 = automatisch)",
            min_value=0,
            max_value=20,
            value=0,
            step=1,
            help="Wenn die Anzahl bekannt ist, verbessert das die Genauigkeit.",
        ))
        hf_token = st.sidebar.text_input(
            "HuggingFace Token",
            value=os.getenv("HF_TOKEN", ""),
            type="password",
            help=(
                "Benötigt für pyannote/speaker-diarization-3.1.\n"
                "Erstellen unter: huggingface.co/settings/tokens"
            ),
        )

    st.sidebar.divider()

    # --- Ollama model selection with refresh button ---
    hdr_col, btn_col = st.sidebar.columns([4, 1])
    hdr_col.markdown("**Ollama-Modell**")
    if btn_col.button("↻", help="Modell-Liste neu laden", key="refresh_ollama"):
        st.session_state["ollama_models"] = None

    if st.session_state["ollama_models"] is None:
        try:
            st.session_state["ollama_models"] = LLMProcessor(OLLAMA_BASE_URL).get_available_models()
        except LLMError:
            st.session_state["ollama_models"] = []

    ollama_models: list[str] = st.session_state["ollama_models"]
    if ollama_models:
        ollama_model: str = st.sidebar.selectbox(
            "Ollama-Modell wählen",
            options=ollama_models,
            label_visibility="collapsed",
        )  # type: ignore[assignment]
    else:
        st.sidebar.warning("Keine Modelle gefunden. Läuft `ollama serve`?")
        ollama_model = st.sidebar.text_input(
            "Modellname manuell",
            value="llama3",
            label_visibility="collapsed",
        )

    task_label: str = st.sidebar.selectbox(
        "Ausgabeformat",
        options=list(_TASK_LABELS.keys()),
        help="Bestimmt, wie das Transkript vom LLM aufbereitet wird.",
    )  # type: ignore[assignment]
    task = _TASK_LABELS[task_label]
    st.sidebar.caption(_TASK_DESCRIPTIONS[task])

    custom_prompt = ""
    if task == "custom":
        custom_prompt = st.sidebar.text_area(
            "Eigener Prompt",
            placeholder="Dein Prompt… {text} wird durch das Transkript ersetzt.",
            height=120,
            max_chars=4000,
        )

    st.sidebar.divider()
    _render_vram_info()

    return {
        "model_size": model_size,
        "language": language,
        "use_diarization": use_diarization,
        "num_speakers": num_speakers,
        "hf_token": hf_token,
        "ollama_model": ollama_model,
        "task": task,
        "custom_prompt": custom_prompt,
    }


# ---------------------------------------------------------------------------
# VRAM info widget
# ---------------------------------------------------------------------------

def _render_vram_info() -> None:
    """Show GPU name and live VRAM usage as a progress bar in the sidebar."""
    if not torch.cuda.is_available():
        st.sidebar.info(
            f"GPU: nicht verfügbar – läuft auf **CPU**\n\n"
            f"compute_type: `{WHISPER_COMPUTE_TYPE}` (int8 empfohlen für CPU)"
        )
        return

    props = torch.cuda.get_device_properties(0)
    total_gb = props.total_memory / 1024**3
    reserved_gb = torch.cuda.memory_reserved(0) / 1024**3
    allocated_gb = torch.cuda.memory_allocated(0) / 1024**3
    free_gb = total_gb - reserved_gb
    used_pct = reserved_gb / total_gb if total_gb > 0 else 0.0

    st.sidebar.markdown(f"**GPU:** {props.name}")
    st.sidebar.progress(
        used_pct,
        text=f"VRAM: {reserved_gb:.1f} GB reserviert / {total_gb:.1f} GB  ({free_gb:.1f} GB frei)",
    )
    st.sidebar.caption(
        f"Allokiert: {allocated_gb:.2f} GB  ·  compute_type: `{WHISPER_COMPUTE_TYPE}`"
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(audio_path: Path, settings: dict) -> None:
    """Run transcription → diarization → LLM with a live status widget."""

    with st.status("Verarbeite Audio…", expanded=True) as status:

        # ── 1. Transcription ───────────────────────────────────────────────
        st.write("🎙️ Transkribiere Audio…")
        t_bar = st.progress(0.0)

        def on_t_progress(fraction: float, message: str) -> None:
            t_bar.progress(min(fraction, 1.0), text=message)

        try:
            engine = TranscriptionEngine(
                model_size=settings["model_size"],
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
            result = engine.transcribe(
                audio_path,
                language=settings["language"],
                progress_callback=on_t_progress,
            )
            # Unload Whisper BEFORE loading pyannote – 6 GB VRAM can't hold both.
            engine.unload()
        except TranscriptionError as exc:
            status.update(label="Transkription fehlgeschlagen", state="error")
            st.error(f"**Transkriptionsfehler:** {exc}")
            return

        t_bar.progress(1.0, text="Transkription abgeschlossen.")
        segments = result["segments"]

        # ── 2. Speaker diarization (optional) ─────────────────────────────
        if settings["use_diarization"]:
            st.write("👥 Erkenne Sprecher…")
            d_bar = st.progress(0.0, text="Lade Diarisierungs-Pipeline…")
            try:
                diarizer = SpeakerDiarizer(hf_token=settings["hf_token"] or None)
                d_bar.progress(0.3, text="Analysiere Sprecher…")
                num_hint = settings["num_speakers"] if settings["num_speakers"] > 0 else None
                turns = diarizer.diarize(audio_path, num_speakers=num_hint)
                d_bar.progress(0.85, text="Weise Sprecher zu…")
                segments = SpeakerDiarizer.assign_speakers(segments, turns)
                diarizer.unload()
                d_bar.progress(1.0, text="Sprechererkennung abgeschlossen.")
            except DiarizationError as exc:
                d_bar.progress(1.0, text="Übersprungen.")
                st.warning(
                    f"**Sprechererkennung übersprungen** – Transkript ohne Sprecher-Labels.\n\n"
                    f"Ursache: {exc}"
                )
                # Non-fatal: keep going without speaker labels.

        # ── 3. LLM analysis ────────────────────────────────────────────────
        st.write("🤖 Analysiere mit KI…")
        l_bar = st.progress(0.0, text="Sende Anfrage an Ollama…")
        llm_output = ""
        try:
            formatted_text = LLMProcessor.format_transcript_for_llm(segments)
            llm_output = LLMProcessor(OLLAMA_BASE_URL).process(
                text=formatted_text,
                task=settings["task"],  # type: ignore[arg-type]
                model=settings["ollama_model"],
                custom_prompt=settings["custom_prompt"] or None,
            )
            l_bar.progress(1.0, text="KI-Analyse abgeschlossen.")
        except (LLMError, ValueError) as exc:
            l_bar.progress(1.0, text="Übersprungen.")
            st.warning(f"**KI-Analyse übersprungen:** {exc}")

        # ── Persist results (single atomic write – no partial state on rerun) ─
        st.session_state.update(
            segments=segments,
            transcription_meta={
                "language": result["language"],
                "duration": result["duration"],
                "filename": audio_path.name,
            },
            llm_output=llm_output,
        )
        status.update(label="Verarbeitung abgeschlossen ✓", state="complete", expanded=False)


# ---------------------------------------------------------------------------
# Result tabs
# ---------------------------------------------------------------------------

def _speaker_color(speaker: str) -> str:
    """Return a colour for a speaker that stays the same across app restarts."""
    return speaker_color(speaker, _SPEAKER_COLORS)


def _render_transcript_tab(segments: list[dict]) -> None:
    rows: list[str] = []

    for seg in segments:
        ts = TranscriptionEngine.format_timestamp(seg["start"])
        text = _html.escape(seg.get("text", "").strip())
        if not text:
            continue
        speaker = seg.get("speaker", "")
        ts_html = (
            f'<span style="color:#999;font-size:0.8em;font-family:monospace">[{ts}]</span>'
        )
        if speaker:
            color = _speaker_color(speaker)
            badge = (
                f'<span style="background:{color};color:#fff;padding:2px 10px;'
                f'border-radius:12px;font-size:0.8em;font-weight:600;'
                f'white-space:nowrap">{_html.escape(speaker)}</span>'
            )
            rows.append(
                f'<div style="padding:5px 2px;border-bottom:1px solid #f0f0f0;line-height:1.7">'
                f'{badge}&nbsp;{ts_html}&nbsp;{text}</div>'
            )
        else:
            rows.append(
                f'<div style="padding:5px 2px;border-bottom:1px solid #f0f0f0;line-height:1.7">'
                f'{ts_html}&nbsp;{text}</div>'
            )

    if rows:
        st.markdown(
            '<div style="max-height:620px;overflow-y:auto;padding:4px 6px">'
            + "".join(rows)
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Keine Textsegmente gefunden.")


def _render_llm_tab(llm_output: str, segments: list[dict], settings: dict) -> None:
    if llm_output:
        # Remote image references in the model output would make the browser
        # fetch them – an outbound request nobody asked for.
        st.markdown(strip_remote_images(llm_output))
    else:
        st.info("Kein KI-Ergebnis vorhanden. Starte die Analyse unten neu.")

    st.divider()
    st.subheader("Erneut analysieren")

    col_task, col_btn = st.columns([3, 1])
    rerun_label: str = col_task.selectbox(
        "Aufgabe wählen",
        options=list(_TASK_LABELS.keys()),
        key="rerun_task_select",
        label_visibility="collapsed",
    )  # type: ignore[assignment]
    rerun_task = _TASK_LABELS[rerun_label]

    rerun_custom = ""
    if rerun_task == "custom":
        rerun_custom = st.text_area(
            "Eigener Prompt",
            key="rerun_custom_prompt",
            placeholder="{text} wird durch das Transkript ersetzt.",
        )

    if col_btn.button("Analysieren", key="btn_rerun_llm", type="primary", use_container_width=True):
        with st.spinner("Analysiere…"):
            try:
                formatted = LLMProcessor.format_transcript_for_llm(segments)
                output = LLMProcessor(OLLAMA_BASE_URL).process(
                    text=formatted,
                    task=rerun_task,  # type: ignore[arg-type]
                    model=settings["ollama_model"],
                    custom_prompt=rerun_custom or None,
                )
                st.session_state["llm_output"] = output
                st.rerun()
            except (LLMError, ValueError) as exc:
                st.error(f"Fehler: {exc}")


def task_label_for(task: str) -> str:
    """Return the human-readable label for a task key."""
    return next((lbl for lbl, key in _TASK_LABELS.items() if key == task), task)


def _render_export_tab(
    segments: list[dict], meta: dict, llm_output: str, task: str
) -> None:
    stem = Path(meta.get("filename", "transkript")).stem
    today = date.today().isoformat()              # "2024-01-15"
    task_slug = _TASK_FILE_SUFFIX.get(task, "analyse")

    st.subheader("Transkript exportieren")
    col1, col2 = st.columns(2)

    col1.download_button(
        label="📄 Transkript als .txt",
        data=LLMProcessor.format_transcript_for_llm(segments).encode("utf-8"),
        file_name=f"{stem}_transkript_{today}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    json_payload = {
        "filename": meta.get("filename", ""),
        "language": meta.get("language", ""),
        "duration": meta.get("duration", 0),
        "segments": segments,
    }
    col2.download_button(
        label="📦 Transkript als .json",
        data=json.dumps(json_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{stem}_transkript_{today}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.subheader("KI-Analyse exportieren")
    if llm_output:
        st.download_button(
            label=f"📝 {task_label_for(task)} als .txt",
            data=llm_output.encode("utf-8"),
            file_name=f"{stem}_{task_slug}_{today}.txt",
            mime="text/plain",
        )
    else:
        st.info("Kein KI-Ergebnis zum Exportieren vorhanden.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _init_state()
    settings = _render_sidebar()

    st.title("🎙️ LocalTranscribe")
    st.caption("Lokales Speech-to-Text mit Sprechererkennung & KI-Analyse")

    # ── Audio input: two tabs ──────────────────────────────────────────────
    # Each tab populates its own local. Priority at the end: upload > recording.
    _upload_bytes: bytes | None = None
    _upload_name: str | None = None

    tab_upload, tab_record = st.tabs(["📁 Datei hochladen", "🎤 Aufnehmen"])

    # --- Upload tab ---
    with tab_upload:
        uploaded = st.file_uploader(
            "Audiodatei hochladen",
            type=_ACCEPT,
            help=f"Unterstützte Formate: {', '.join(SUPPORTED_FORMATS)}",
        )
        if uploaded is not None:
            file_id = (uploaded.name, uploaded.size)
            if file_id != st.session_state["last_file_id"]:
                # New file: drop stale results and make the upload the active
                # input. The recording's own tracking key stays untouched.
                _reset_results()
                st.session_state.update(last_file_id=file_id, active_source="upload")
            _upload_bytes = uploaded.getvalue()
            _upload_name = uploaded.name

    # --- Record tab ---
    with tab_record:
        try:
            from st_audiorec import st_audiorec
            _has_audiorec = True
        except ImportError:
            _has_audiorec = False

        if not _has_audiorec:
            st.warning(
                "`st-audiorec` ist nicht installiert.\n\n"
                "```\npip install st-audiorec\n```"
            )
        else:
            st.caption("▶ **Start** drücken · sprechen · ■ **Stop** drücken")
            wav_bytes: bytes | None = st_audiorec()

            # st_audiorec returns bytes only on the one rerun after Stop is pressed.
            # Persist them in session state so playback survives further reruns.
            if wav_bytes is not None and len(wav_bytes) > 100:  # 100 B > bare WAV header
                rec_id = len(wav_bytes)
                if rec_id != st.session_state["rec_audio_id"]:
                    # New recording: drop stale results and make the recording
                    # the active input. The upload's tracking key stays as is.
                    _reset_results()
                    st.session_state.update(
                        rec_audio_bytes=wav_bytes,
                        rec_audio_id=rec_id,
                        active_source="record",
                    )

            stored_rec: bytes | None = st.session_state["rec_audio_bytes"]
            if stored_rec is not None:
                st.audio(stored_rec, format="audio/wav")
                st.caption(f"Aufnahme bereit · {len(stored_rec) / 1024:.0f} KB")
            elif wav_bytes is None:
                st.info("Noch keine Aufnahme. Drücke **Start** oben.")

    # ── Resolve active audio source ────────────────────────────────────────
    # Whichever input the user touched last wins; if that one is gone, fall
    # back to the other. No block ever clears the other's state.
    _rec_bytes: bytes | None = st.session_state["rec_audio_bytes"]
    audio_bytes: bytes | None = None
    audio_name: str = ""

    if st.session_state["active_source"] == "record" and _rec_bytes is not None:
        audio_bytes, audio_name = _rec_bytes, "browser-aufnahme.wav"
    elif _upload_bytes is not None:
        audio_bytes, audio_name = _upload_bytes, (_upload_name or "audio")
    elif _rec_bytes is not None:
        audio_bytes, audio_name = _rec_bytes, "browser-aufnahme.wav"

    # ── Pipeline trigger ───────────────────────────────────────────────────
    if audio_bytes is not None:
        info_col, btn_col = st.columns([4, 1])
        size_kb = len(audio_bytes) / 1024
        info_col.markdown(f"**Audio:** `{audio_name}` &nbsp;·&nbsp; {size_kb:.0f} KB")
        run_pipeline = btn_col.button(
            "▶ Transkribieren", type="primary", use_container_width=True
        )

        if run_pipeline:
            suffix = Path(audio_name).suffix or ".wav"
            fd, tmp_str = tempfile.mkstemp(suffix=suffix)
            tmp_path = Path(tmp_str)
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(audio_bytes)
                fd = -1  # fdopen took ownership; fd is now closed
                _run_pipeline(tmp_path, settings)
            except Exception as exc:  # noqa: BLE001 – surface, never crash the UI
                if fd != -1:
                    os.close(fd)  # safety net if fdopen itself raised
                logger.exception("Pipeline failed for '%s'", audio_name)
                st.error(
                    f"**Verarbeitung fehlgeschlagen:** {exc}\n\n"
                    "Details stehen im Konsolenfenster."
                )
            finally:
                tmp_path.unlink(missing_ok=True)
    else:
        st.info("Lade eine Audiodatei hoch oder nimm Audio auf, um zu beginnen.")

    # ── Results ────────────────────────────────────────────────────────────
    segments: list[dict] | None = st.session_state["segments"]
    meta: dict | None = st.session_state["transcription_meta"]
    llm_output: str = st.session_state["llm_output"] or ""

    if segments is not None and meta is not None:
        st.divider()

        duration_str = TranscriptionEngine.format_timestamp(meta.get("duration", 0))
        lang = (meta.get("language") or "?").upper()
        n_segs = len(segments)
        speakers = {
            s["speaker"] for s in segments
            if s.get("speaker") and s["speaker"] not in ("Unbekannt",)
        }
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Dauer", duration_str)
        m2.metric("Sprache", lang)
        m3.metric("Segmente", n_segs)
        m4.metric("Sprecher", len(speakers) if speakers else "–")

        tab_t, tab_llm, tab_export = st.tabs(["📝 Transkript", "🤖 KI-Analyse", "💾 Export"])

        with tab_t:
            _render_transcript_tab(segments)

        with tab_llm:
            _render_llm_tab(llm_output, segments, settings)

        with tab_export:
            _render_export_tab(segments, meta, llm_output, settings["task"])


if __name__ == "__main__":
    main()
