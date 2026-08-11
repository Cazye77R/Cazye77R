"""
Whisper-based audio transcription using faster-whisper.

Handles loading the Whisper model and transcribing audio files
into timestamped segments with word-level confidence scores.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

import torch
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment

from config import WHISPER_COMPUTE_TYPE, WHISPER_COMPUTE_TYPE_FALLBACK, WHISPER_DEVICE, WHISPER_MODEL
from utils import format_timestamp as _format_timestamp

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when transcription fails due to an unreadable file or model error."""


class TranscriptionEngine:
    """Transcribes audio files using a local Whisper model via faster-whisper."""

    def __init__(
        self,
        model_size: str = WHISPER_MODEL,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
    ) -> None:
        """
        Load the Whisper model onto the target device.

        Args:
            model_size: Whisper model variant (e.g. "large-v3").
            device: Compute device ("cuda" or "cpu").
            compute_type: Precision type ("float16", "int8", etc.).

        Raises:
            TranscriptionError: If the model cannot be loaded.
        """
        self.model_size = model_size

        # Resolve device: honour the caller's preference but silently fall
        # back to CPU when CUDA is requested but the runtime has no GPU.
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available – falling back to CPU.")
            device = "cpu"
            compute_type = WHISPER_COMPUTE_TYPE_FALLBACK

        # _load_model may move us to the CPU when the GPU runs out of memory,
        # so the effective device/compute type come back from the loader.
        self.model, self.device, self.compute_type = self._load_model(
            model_size, device, compute_type
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str | os.PathLike,
        language: str = "de",
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> dict:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file.
            language: BCP-47 language code (e.g. "de", "en").  Always passed
                      explicitly to faster-whisper; never left as None, which
                      would trigger slower auto-detection and can hurt accuracy.
                      Defaults to "de".
            progress_callback: Optional callable(fraction: float, message: str)
                               invoked after each segment; used to update a
                               Streamlit progress bar.

        Returns:
            Dict with keys:
              - "segments": list of {start, end, text, words}
              - "language": detected/requested language code
              - "duration": total audio duration in seconds

        Raises:
            TranscriptionError: If the file is unreadable or transcription fails.
        """
        if self.model is None:
            raise TranscriptionError(
                "Whisper model was unloaded – create a new TranscriptionEngine "
                "before transcribing again."
            )

        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        # Always use an explicit language code; fall back to "de" if caller
        # passes an empty string or a legacy "auto" value.
        lang_arg = language if language and language != "auto" else "de"

        vad_parameters = {
            "min_silence_duration_ms": 500,
        }

        try:
            segments_iter, info = self.model.transcribe(
                str(audio_path),
                language=lang_arg,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=vad_parameters,
            )
        except Exception as exc:
            raise TranscriptionError(f"Transcription failed for '{audio_path.name}': {exc}") from exc

        segments: list[dict] = []
        total_duration = info.duration or 1.0  # guard against zero

        try:
            for segment in segments_iter:
                seg_dict = self._segment_to_dict(segment)
                segments.append(seg_dict)

                if progress_callback is not None:
                    fraction = min(segment.end / total_duration, 1.0)
                    progress_callback(fraction, f"Segment {len(segments)}: {segment.start:.1f}s – {segment.end:.1f}s")
        except Exception as exc:
            segments.clear()  # discard partial results; caller gets an error, not silent partial data
            raise TranscriptionError(f"Error while reading segments: {exc}") from exc
        finally:
            # Always free GPU memory, even if an exception occurred mid-stream.
            if self.device == "cuda":
                torch.cuda.empty_cache()
                logger.debug("GPU cache cleared.")

        if progress_callback is not None:
            progress_callback(1.0, "Transcription complete.")

        return {
            "segments": segments,
            "language": info.language,
            "duration": info.duration,
        }

    def unload(self) -> None:
        """
        Delete the model reference and free GPU memory.

        Call this before constructing SpeakerDiarizer on a 6 GB GPU – both
        models cannot coexist in VRAM at the same time.
        """
        if self.model is not None:
            del self.model
            self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Whisper model unloaded.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_model(
        model_size: str, device: str, compute_type: str
    ) -> tuple[WhisperModel, str, str]:
        """
        Load WhisperModel, falling back to the CPU on a CUDA out-of-memory.

        int8 is already the most memory-frugal GPU precision this project uses,
        so there is no lighter precision to retry with – the meaningful escape
        from an OOM is to move off the GPU entirely.

        Returns:
            (model, effective_device, effective_compute_type)
        """
        try:
            logger.info("Loading Whisper '%s' on %s (%s)…", model_size, device, compute_type)
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model ready.")
            return model, device, compute_type
        except RuntimeError as exc:
            oom = "out of memory" in str(exc).lower()
            if oom and device == "cuda":
                logger.warning(
                    "CUDA OOM loading '%s' (%s) – retrying on CPU with '%s'.",
                    model_size,
                    compute_type,
                    WHISPER_COMPUTE_TYPE_FALLBACK,
                )
                torch.cuda.empty_cache()
                try:
                    model = WhisperModel(
                        model_size,
                        device="cpu",
                        compute_type=WHISPER_COMPUTE_TYPE_FALLBACK,
                    )
                    logger.info("Whisper model ready on CPU (slower, but it fits).")
                    return model, "cpu", WHISPER_COMPUTE_TYPE_FALLBACK
                except Exception as inner:
                    raise TranscriptionError(
                        f"Whisper failed on GPU (out of memory) and on CPU: {inner}"
                    ) from inner
            raise TranscriptionError(f"Failed to load Whisper model '{model_size}': {exc}") from exc
        except Exception as exc:
            raise TranscriptionError(f"Failed to load Whisper model '{model_size}': {exc}") from exc

    @staticmethod
    def format_timestamp(seconds: float | None) -> str:
        """
        Convert a duration in seconds to "HH:MM:SS".

        Delegates to utils.format_timestamp so the LLM layer can format
        timestamps identically without importing torch.

        Args:
            seconds: Duration in seconds; None and negative values yield
                     "00:00:00".

        Returns:
            Zero-padded timestamp string, e.g. "01:23:45".
        """
        return _format_timestamp(seconds)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _segment_to_dict(segment: Segment) -> dict:
        """Convert a faster-whisper Segment namedtuple to a plain dict."""
        words = []
        if segment.words:
            for w in segment.words:
                words.append({
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "word": w.word,
                    "probability": round(w.probability, 4),
                })
        return {
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": segment.text.strip(),
            "words": words,
        }


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    wav_path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"

    def on_progress(fraction: float, message: str) -> None:
        bar_len = 40
        filled = int(bar_len * fraction)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r[{bar}] {fraction * 100:5.1f}%  {message}", end="", flush=True)

    engine = TranscriptionEngine()  # uses the configured model/device/precision

    print(f"Transcribing: {wav_path}\n")
    result = engine.transcribe(wav_path, language="de", progress_callback=on_progress)
    print()  # newline after progress bar

    print(f"\nDetected language : {result['language']}")
    print(f"Duration          : {TranscriptionEngine.format_timestamp(result['duration'])}")
    print(f"Segments          : {len(result['segments'])}\n")

    for seg in result["segments"]:
        ts = TranscriptionEngine.format_timestamp(seg["start"])
        print(f"[{ts}]  {seg['text']}")

    out_path = Path(wav_path).stem + "_transcript.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"\nFull result saved to: {out_path}")
