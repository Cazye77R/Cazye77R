"""
Speaker diarization using pyannote.audio.

Identifies and labels individual speakers in an audio file,
then merges the resulting speaker turns with Whisper transcription segments.
"""

# TODO: from pyannote.audio import Pipeline
# TODO: import os, dotenv for HF_TOKEN loading


class Diarizer:
    """Assigns speaker labels to transcription segments via pyannote.audio."""

    def __init__(self, hf_token: str = None):
        """
        Initialize the pyannote speaker diarization pipeline.

        Args:
            hf_token: HuggingFace access token for gated model download.
                      Falls back to the HF_TOKEN environment variable.
        """
        # TODO: load .env and read HF_TOKEN if hf_token is None
        # TODO: load Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", ...)
        # TODO: send pipeline to GPU if available
        pass

    def diarize(self, audio_path: str) -> list[dict]:
        """
        Run diarization on an audio file.

        Args:
            audio_path: Path to the audio file.

        Returns:
            List of turn dicts with keys: start, end, speaker.
        """
        # TODO: call pipeline(audio_path) to get diarization annotation
        # TODO: iterate itertracks(yield_label=True) and collect turns
        # TODO: return list of {start, end, speaker} dicts
        pass

    def merge_with_transcript(
        self, segments: list[dict], turns: list[dict]
    ) -> list[dict]:
        """
        Assign speaker labels to transcription segments by time overlap.

        Args:
            segments: Transcription segments from Transcriber.transcribe().
            turns: Speaker turns from Diarizer.diarize().

        Returns:
            Transcription segments enriched with a "speaker" key.
        """
        # TODO: for each segment find the turn with maximum time overlap
        # TODO: attach speaker label (or "Unknown") to each segment
        # TODO: return enriched segment list
        pass
