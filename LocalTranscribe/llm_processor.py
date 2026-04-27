"""
LLM post-processing via a local Ollama instance.

Formats transcription segments into readable text and sends them to an
Ollama model for summarisation, topic analysis, meeting-protocol generation,
or arbitrary custom prompts.
"""

from __future__ import annotations

import logging
from typing import Literal

import requests

from config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

Task = Literal[
    "zusammenfassung",
    "themen",
    "protokoll",
    "bericht",
    "massnahmen",
    "faq",
    "stichpunkte",
    "custom",
]

_PROMPTS: dict[str, dict[str, str]] = {
    "zusammenfassung": {
        "system": "Du bist ein präziser Assistent. Antworte immer auf Deutsch.",
        "user": (
            "Fasse das folgende Transkript zusammen. "
            "Nenne die wichtigsten Punkte und Ergebnisse:\n\n{text}"
        ),
    },
    "themen": {
        "system": "Du bist ein Analyst. Antworte auf Deutsch in strukturierter Form.",
        "user": (
            "Analysiere das folgende Transkript und sortiere den Inhalt nach Themen. "
            "Liste jeden Themenbereich mit den zugehörigen Aussagen auf:\n\n{text}"
        ),
    },
    "protokoll": {
        "system": "Du bist ein professioneller Protokollführer. Antworte auf Deutsch.",
        "user": (
            "Erstelle ein Meeting-Protokoll aus dem folgenden Transkript. "
            "Gliedere es in: Teilnehmer, besprochene Themen, Entscheidungen, "
            "offene Punkte und nächste Schritte:\n\n{text}"
        ),
    },
    "bericht": {
        "system": "Du bist ein professioneller technischer Redakteur. Antworte auf Deutsch.",
        "user": (
            "Erstelle einen strukturierten Bericht aus dem folgenden Transkript. "
            "Gliedere ihn in: 1. Zusammenfassung, 2. Detaillierte Inhalte, "
            "3. Ergebnisse/Erkenntnisse, 4. Empfehlungen (falls ableitbar). "
            "Schreibe in sachlichem, professionellem Stil:\n\n{text}"
        ),
    },
    "massnahmen": {
        "system": "Du bist ein Projektmanagement-Assistent. Antworte auf Deutsch.",
        "user": (
            "Extrahiere alle Aufgaben, Maßnahmen, Entscheidungen und Verantwortlichkeiten "
            "aus dem folgenden Transkript. Formatiere als Liste mit: "
            "Aufgabe, Verantwortlich (Sprecher), Frist (falls genannt):\n\n{text}"
        ),
    },
    "faq": {
        "system": "Du bist ein Analyst. Antworte auf Deutsch.",
        "user": (
            "Extrahiere alle Fragen und die dazugehörigen Antworten aus dem folgenden "
            "Transkript. Formatiere als Q&A-Liste:\n\n{text}"
        ),
    },
    "stichpunkte": {
        "system": "Du bist ein präziser Assistent. Antworte auf Deutsch.",
        "user": (
            "Fasse das folgende Transkript als kompakte Stichpunktliste zusammen. "
            "Maximal 15 Stichpunkte, nur die Kernaussagen:\n\n{text}"
        ),
    },
}


class LLMError(Exception):
    """Raised when the Ollama API returns an error or is unreachable."""


class LLMProcessor:
    """Sends formatted transcripts to a local Ollama model for analysis."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL) -> None:
        """
        Args:
            base_url: Ollama API base URL (e.g. "http://localhost:11434").
        """
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_available_models(self) -> list[str]:
        """
        Return the list of locally pulled Ollama model names.

        Returns:
            Sorted list of model name strings (e.g. ["llama3:latest", "mistral"]).

        Raises:
            LLMError: If Ollama is not running or the request fails.
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise LLMError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is 'ollama serve' running?"
            ) from exc
        except requests.HTTPError as exc:
            raise LLMError(f"Ollama /api/tags returned an error: {exc}") from exc

        models = [m["name"] for m in response.json().get("models", [])]
        return sorted(models)

    def process(
        self,
        text: str,
        task: Task,
        model: str,
        custom_prompt: str | None = None,
    ) -> str:
        """
        Run a predefined or custom LLM task against the transcript text.

        Args:
            text: Formatted transcript text (use format_transcript_for_llm()).
            task: One of "zusammenfassung", "themen", "protokoll", "custom".
            model: Ollama model tag to use (e.g. "llama3", "mistral").
            custom_prompt: Required when task="custom"; used as the full user
                           prompt.  {text} is replaced with the transcript if
                           the placeholder is present, otherwise the transcript
                           is appended after a blank line.

        Returns:
            Model-generated response string.

        Raises:
            ValueError: If task is unknown or custom_prompt is missing for
                        task="custom".
            LLMError: If the Ollama request fails or times out.
        """
        system_prompt, user_prompt = self._build_prompts(text, task, custom_prompt)
        return self._generate(model=model, system=system_prompt, prompt=user_prompt)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_transcript_for_llm(segments: list[dict]) -> str:
        """
        Convert transcription segments into a readable plain-text transcript.

        Format with speaker labels (if present):
            Sprecher 1 [00:01:23]: Das war ein gutes Meeting.

        Format without speaker labels:
            [00:01:23] Das war ein gutes Meeting.

        Args:
            segments: Output of TranscriptionEngine.transcribe()["segments"],
                      optionally enriched by SpeakerDiarizer.assign_speakers().

        Returns:
            Multi-line string ready to be embedded in an LLM prompt.
        """
        lines: list[str] = []
        for seg in segments:
            ts = _format_timestamp(seg["start"])
            text = seg.get("text", "").strip()
            if not text:
                continue
            speaker = seg.get("speaker")
            if speaker:
                lines.append(f"{speaker} [{ts}]: {text}")
            else:
                lines.append(f"[{ts}] {text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompts(
        self,
        text: str,
        task: Task,
        custom_prompt: str | None,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the given task."""
        if task == "custom":
            if not custom_prompt:
                raise ValueError("custom_prompt must be provided when task='custom'.")
            system = "Du bist ein hilfreicher Assistent. Antworte auf Deutsch."
            if "{text}" in custom_prompt:
                user = custom_prompt.replace("{text}", text)
            else:
                user = f"{custom_prompt}\n\n{text}"
            return system, user

        if task not in _PROMPTS:
            raise ValueError(
                f"Unknown task '{task}'. "
                f"Valid tasks: {list(_PROMPTS.keys()) + ['custom']}"
            )

        template = _PROMPTS[task]
        return template["system"], template["user"].format(text=text)

    def _generate(self, model: str, system: str, prompt: str) -> str:
        """
        POST to /api/generate and return the response text.

        Args:
            model: Ollama model tag.
            system: System-role prompt.
            prompt: User-role prompt.

        Raises:
            LLMError: On connection failure, HTTP error, or timeout.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }

        logger.info("Sending task to Ollama model '%s' at %s…", model, self.base_url)

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise LLMError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is 'ollama serve' running?"
            ) from exc
        except requests.Timeout as exc:
            raise LLMError(
                f"Ollama request timed out after 120 s. "
                "Try a smaller model or shorten the transcript."
            ) from exc
        except requests.HTTPError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            raise LLMError(f"Ollama returned HTTP {exc.response.status_code}: {body}") from exc

        result: str = response.json().get("response", "")
        logger.info("LLM response received (%d chars).", len(result))
        return result.strip()


# ---------------------------------------------------------------------------
# Timestamp helper (mirrors TranscriptionEngine.format_timestamp)
# ---------------------------------------------------------------------------

def _format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_s = int(seconds)
    hours, remainder = divmod(total_s, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    base_url = sys.argv[1] if len(sys.argv) > 1 else OLLAMA_BASE_URL

    processor = LLMProcessor(base_url=base_url)

    print("=== Ollama connection test ===")
    try:
        models = processor.get_available_models()
    except LLMError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if not models:
        print("No models found locally.  Run: ollama pull llama3")
        sys.exit(1)

    print(f"Available models: {models}")
    model = models[0]
    print(f"Using: {model}\n")

    # Fake transcript with speaker labels
    fake_segments = [
        {"start": 0.0,  "end": 5.2,  "text": "Guten Morgen, fangen wir an.",       "speaker": "Sprecher 1"},
        {"start": 5.5,  "end": 12.1, "text": "Das Budget für Q3 liegt bei 50.000.", "speaker": "Sprecher 2"},
        {"start": 12.4, "end": 18.0, "text": "Gut, dann plane ich entsprechend.",   "speaker": "Sprecher 1"},
        {"start": 18.3, "end": 25.7, "text": "Nächste Woche Statusmeeting?",        "speaker": "Sprecher 2"},
        {"start": 26.0, "end": 30.5, "text": "Ja, Dienstag 10 Uhr.",                "speaker": "Sprecher 1"},
    ]

    formatted = LLMProcessor.format_transcript_for_llm(fake_segments)
    print("--- Formatted transcript ---")
    print(formatted)
    print()

    for task in ("zusammenfassung", "themen", "protokoll"):
        print(f"--- Task: {task} ---")
        try:
            output = processor.process(formatted, task=task, model=model)  # type: ignore[arg-type]
            print(output[:500])
            if len(output) > 500:
                print(f"… ({len(output)} chars total)")
        except LLMError as exc:
            print(f"ERROR: {exc}")
        print()

    print("--- Task: custom ---")
    try:
        output = processor.process(
            formatted,
            task="custom",
            model=model,
            custom_prompt="Zähle alle genannten Zahlen und Daten auf:\n\n{text}",
        )
        print(output)
    except LLMError as exc:
        print(f"ERROR: {exc}")
