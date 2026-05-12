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

        self.device = device
        self.compute_type = compute_type

        self.model: WhisperModel | None = self._load_model(model_size, device, compute_type)

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
    ) -> WhisperModel:
        """
        Load WhisperModel with automatic int8 retry on CUDA out-of-memory.

        If the requested compute_type triggers a CUDA OOM (common with
        float16 on 6 GB GPUs for large-v3), the cache is cleared and the
        model is reloaded with int8 quantisation.
        """
        try:
            logger.info("Loading Whisper '%s' on %s (%s)…", model_size, device, compute_type)
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model ready.")
            return model
        except RuntimeError as exc:
            oom = "out of memory" in str(exc).lower()
            if oom and device == "cuda" and compute_type != WHISPER_COMPUTE_TYPE_FALLBACK:
                logger.warning(
                    "CUDA OOM with compute_type='%s' – retrying with '%s'.",
                    compute_type,
                    WHISPER_COMPUTE_TYPE_FALLBACK,
                )
                torch.cuda.empty_cache()
                try:
                    model = WhisperModel(
                        model_size,
                        device=device,
                        compute_type=WHISPER_COMPUTE_TYPE_FALLBACK,
                    )
                    logger.info("Whisper model ready (fallback compute_type).")
                    return model
                except Exception as inner:
                    raise TranscriptionError(
                        f"Whisper OOM even with '{WHISPER_COMPUTE_TYPE_FALLBACK}': {inner}"
                    ) from inner
            raise TranscriptionError(f"Failed to load Whisper model '{model_size}': {exc}") from exc
        except Exception as exc:
            raise TranscriptionError(f"Failed to load Whisper model '{model_size}': {exc}") from exc

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Convert a duration in seconds to "HH:MM:SS".

        Args:
            seconds: Non-negative duration in seconds.

        Returns:
            Zero-padded timestamp string, e.g. "01:23:45".
        """
        seconds = max(0.0, seconds)
        total_s = int(seconds)
        hours, remainder = divmod(total_s, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

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

    engine = TranscriptionEngine(model_size="large-v3", device="cuda", compute_type="float16")

    print(f"Transcribing: {wav_path}\n")
    result = engine.transcribe(wav_path, language="auto", progress_callback=on_progress)
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
