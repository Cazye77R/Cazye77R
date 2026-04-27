"""
Whisper-based audio transcription using faster-whisper.

Handles loading the Whisper model and transcribing audio files
into timestamped segments with word-level confidence scores.
"""

# TODO: import faster_whisper
# TODO: import config constants (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)


class Transcriber:
    """Transcribes audio files using a local Whisper model via faster-whisper."""

    def __init__(self, model_name: str = None, device: str = None, compute_type: str = None):
        """
        Initialize the Whisper transcription model.

        Args:
            model_name: Whisper model variant (e.g. "large-v3").
            device: Compute device ("cuda" or "cpu").
            compute_type: Precision type ("float16", "int8", etc.).
        """
        # TODO: fall back to config defaults when args are None
        # TODO: load WhisperModel from faster_whisper
        pass

    def transcribe(self, audio_path: str, language: str = "de") -> list[dict]:
        """
        Transcribe an audio file and return timestamped segments.

        Args:
            audio_path: Path to the audio file.
            language: BCP-47 language code; defaults to German ("de").

        Returns:
            List of segment dicts with keys: start, end, text, words.
        """
        # TODO: call model.transcribe() with beam_size and language
        # TODO: iterate segments and collect {start, end, text, words}
        # TODO: return list of segment dicts
        pass
