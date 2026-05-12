"""
Speaker diarization using pyannote.audio.

Identifies and labels individual speakers in an audio file, then maps each
transcription segment to its speaker via midpoint lookup.

VRAM note (RTX 3060, 6 GB):
  pyannote/speaker-diarization-3.1 needs ~2–3 GB.  The Whisper large-v3 model
  needs ~5 GB.  Both cannot coexist on the GPU at the same time.  Callers must
  call TranscriptionEngine.unload() (which deletes the model ref and calls
  torch.cuda.empty_cache()) before constructing SpeakerDiarizer.
"""

from __future__ import annotations

import bisect
import logging
import os
from pathlib import Path

import torch
from dotenv import load_dotenv
from pyannote.audio import Pipeline

logger = logging.getLogger(__name__)

# Maps pyannote's zero-padded IDs to human-readable labels.
# Built lazily in assign_speakers() so it grows with the actual speaker count.
_SPEAKER_LABEL_TEMPLATE = "Sprecher {n}"


class DiarizationError(Exception):
    """Raised when diarization cannot be completed."""


class SpeakerDiarizer:
    """Assigns speaker labels to audio segments via pyannote.audio."""

    def __init__(self, hf_token: str | None = None) -> None:
        """
        Load the pyannote speaker-diarization-3.1 pipeline.

        The pipeline is moved to CUDA if available.  If the token is missing
        or the download is rejected by HuggingFace, a DiarizationError is
        raised immediately so the caller gets a clear message rather than a
        cryptic HTTP 401 deep inside pyannote.

        Args:
            hf_token: HuggingFace access token for the gated model.
                      Falls back to the HF_TOKEN environment variable.

        Raises:
            DiarizationError: If the token is missing or the pipeline fails
                              to load.
        """
        load_dotenv()
        token = hf_token or os.getenv("HF_TOKEN")

        if not token:
            raise DiarizationError(
                "No HuggingFace token found.  Set HF_TOKEN in your .env file "
                "or pass hf_token= explicitly.  A token is required to download "
                "pyannote/speaker-diarization-3.1 (gated model)."
            )

        self._token = token
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Pipeline is intentionally NOT loaded here.  It is loaded lazily in
        # diarize() so that VRAM is only occupied when the pipeline runs.
        # On a 6 GB GPU the Whisper model must be fully unloaded first.
        self._pipeline: Pipeline | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diarize(
        self,
        audio_path: str | os.PathLike,
        num_speakers: int | None = None,
    ) -> list[dict]:
        """
        Run speaker diarization on an audio file.

        Args:
            audio_path: Path to the audio file.
            num_speakers: Optional exact speaker count hint.  When supplied,
                          pyannote skips its own clustering step, which is
                          faster and often more accurate if the count is known.

        Returns:
            Sorted list of dicts: {"start": float, "end": float, "speaker": str}

        Raises:
            DiarizationError: If the file is missing or the pipeline errors.
        """
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise DiarizationError(f"Audio file not found: {audio_path}")

        self._ensure_pipeline_loaded()
        assert self._pipeline is not None, "Pipeline failed to load"

        pipeline_kwargs: dict = {}
        if num_speakers is not None:
            pipeline_kwargs["num_speakers"] = num_speakers

        try:
            logger.info("Running diarization on '%s'…", audio_path.name)
            annotation = self._pipeline(str(audio_path), **pipeline_kwargs)
        except Exception as exc:
            raise DiarizationError(f"Diarization failed: {exc}") from exc
        finally:
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
                logger.debug("GPU cache cleared after diarization.")

        turns: list[dict] = [
            {
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "speaker": label,
            }
            for turn, _, label in annotation.itertracks(yield_label=True)
        ]

        turns.sort(key=lambda t: t["start"])
        logger.info("Diarization found %d turns.", len(turns))
        return turns

    def unload(self) -> None:
        """
        Release the pipeline and free GPU memory.

        Call this after diarization is done so the GPU is available for other
        tasks (e.g. reloading the Whisper model for a second file).
        """
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Diarization pipeline unloaded.")

    def _ensure_pipeline_loaded(self) -> None:
        """Load the pyannote pipeline into VRAM if not already loaded."""
        if self._pipeline is not None:
            return
        try:
            logger.info("Loading pyannote/speaker-diarization-3.1 on %s…", self.device)
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self._token,
            )
            self._pipeline.to(self.device)
            logger.info("Diarization pipeline ready.")
        except Exception as exc:
            raise DiarizationError(
                f"Failed to load diarization pipeline: {exc}\n"
                "Check that your HF_TOKEN is valid and that you have accepted "
                "the model conditions at huggingface.co/pyannote/speaker-diarization-3.1"
            ) from exc

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def assign_speakers(
        transcription_segments: list[dict],
        speaker_segments: list[dict],
    ) -> list[dict]:
        """
        Enrich transcription segments with speaker labels.

        The speaker is determined by which diarization turn contains the
        *midpoint* of each transcription segment.  This is intentionally
        simpler than full overlap integration: midpoint lookup is O(n·m) but
        avoids splitting segments that straddle a speaker boundary, which
        would make the transcript harder to read.

        pyannote labels like "SPEAKER_00" are renamed to "Sprecher 1",
        "SPEAKER_01" → "Sprecher 2", etc., in order of first appearance.

        Args:
            transcription_segments: Output from TranscriptionEngine.transcribe()
                                    (list of {start, end, text, words}).
            speaker_segments: Output from SpeakerDiarizer.diarize()
                              (list of {start, end, speaker}).

        Returns:
            A copy of transcription_segments with a "speaker" key added to
            each segment.  Segments whose midpoint falls in a gap between
            speaker turns are labelled "Unbekannt".
        """
        # Build a stable speaker→label mapping in order of first appearance.
        label_map: dict[str, str] = {}

        def _human_label(raw: str) -> str:
            if raw not in label_map:
                n = len(label_map) + 1
                label_map[raw] = _SPEAKER_LABEL_TEMPLATE.format(n=n)
            return label_map[raw]

        # Pre-sort turns by start time and extract starts for binary search.
        sorted_turns = sorted(speaker_segments, key=lambda t: t["start"])
        starts = [t["start"] for t in sorted_turns]

        result: list[dict] = []

        for seg in transcription_segments:
            midpoint = (seg["start"] + seg["end"]) / 2.0

            # Binary-search: find the rightmost turn whose start ≤ midpoint.
            idx = bisect.bisect_right(starts, midpoint) - 1
            if idx >= 0 and sorted_turns[idx]["end"] >= midpoint:
                matched_speaker = _human_label(sorted_turns[idx]["speaker"])
            else:
                matched_speaker = "Unbekannt"

            result.append({**seg, "speaker": matched_speaker})

        return result


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    wav_path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"

    print("=== Diarization smoke-test ===")
    print(f"File : {wav_path}")

    diarizer = SpeakerDiarizer()  # reads HF_TOKEN from .env

    turns = diarizer.diarize(wav_path, num_speakers=None)

    print(f"\nFound {len(turns)} speaker turns:\n")
    for t in turns[:20]:  # show first 20
        print(f"  [{t['start']:6.2f}s – {t['end']:6.2f}s]  {t['speaker']}")
    if len(turns) > 20:
        print(f"  … ({len(turns) - 20} more turns)")

    # Simulate assign_speakers with a minimal fake transcript segment.
    if turns:
        fake_segments = [
            {"start": turns[0]["start"], "end": turns[0]["end"], "text": "(test)", "words": []}
        ]
        enriched = SpeakerDiarizer.assign_speakers(fake_segments, turns)
        print(f"\nassign_speakers test → speaker = '{enriched[0]['speaker']}'")

    out_path = Path(wav_path).stem + "_diarization.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(turns, fh, ensure_ascii=False, indent=2)
    print(f"\nFull result saved to: {out_path}")

    diarizer.unload()
    print("Pipeline unloaded – GPU memory freed.")
