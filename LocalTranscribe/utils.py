"""
Small dependency-free helpers shared across LocalTranscribe modules.

This module deliberately imports nothing beyond the standard library so it can
be used from both the lightweight LLM layer and the heavy ML layer, and so the
test-suite can exercise it without torch or streamlit installed.
"""

from __future__ import annotations

import re
import zlib

# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def format_timestamp(seconds: float | None) -> str:
    """
    Convert a duration in seconds to "HH:MM:SS".

    Args:
        seconds: Duration in seconds. None, negative and non-numeric values all
                 collapse to "00:00:00" – faster-whisper can report a None
                 duration for streams it cannot measure.

    Returns:
        Zero-padded timestamp string, e.g. "01:23:45".
    """
    try:
        value = max(0.0, float(seconds))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "00:00:00"

    total_s = int(value)
    hours, remainder = divmod(total_s, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Speaker colours
# ---------------------------------------------------------------------------


_TRAILING_NUMBER = re.compile(r"(\d+)\s*$")


def speaker_color(speaker: str, palette: list[str]) -> str:
    """
    Pick a stable colour for a speaker name.

    Labels produced by the diarizer are numbered ("Sprecher 1", "Sprecher 2",
    …), so the trailing number drives the choice. That walks the palette in
    order and gives every speaker a distinct colour until the palette wraps —
    hashing into a small palette collides almost immediately instead (with 8
    slots and 8 speakers a collision is near-certain).

    Unnumbered labels such as "Unbekannt" fall back to crc32, which unlike the
    builtin hash() is not randomised per process — hash() would hand the same
    speaker a different colour after every app restart.

    Args:
        speaker: Speaker label, e.g. "Sprecher 1".
        palette: Non-empty list of CSS colour strings.

    Returns:
        One entry from palette, identical for the same name on every run.
    """
    if not palette:
        raise ValueError("palette must not be empty")

    match = _TRAILING_NUMBER.search(speaker)
    if match:
        return palette[(int(match.group(1)) - 1) % len(palette)]

    return palette[zlib.crc32(speaker.encode("utf-8")) % len(palette)]


# ---------------------------------------------------------------------------
# Output sanitising
# ---------------------------------------------------------------------------

# Markdown image whose target is an absolute URL: ![alt](http://…), https://…
# or the protocol-relative //host/… form.
_REMOTE_IMG_MARKDOWN = re.compile(
    r"!\[([^\]]*)\]\(\s*(?:https?:)?//[^)]*\)",
    re.IGNORECASE,
)

# <img src="http://…"> in raw HTML.
_REMOTE_IMG_HTML = re.compile(
    r"<img\b[^>]*\bsrc\s*=\s*[\"']?\s*(?:https?:)?//[^>]*>",
    re.IGNORECASE,
)


def strip_remote_images(text: str) -> str:
    """
    Neutralise image references that point at remote hosts.

    LLM output is rendered as markdown. A remote image reference in that output
    would make the browser fetch it, opening an outbound request the user never
    asked for. Links are left untouched – they only load when clicked.

    Args:
        text: Raw model output.

    Returns:
        The same text with remote image references replaced by a placeholder.
    """
    if not text:
        return text
    text = _REMOTE_IMG_MARKDOWN.sub(
        lambda m: f"[externes Bild entfernt{': ' + m.group(1) if m.group(1) else ''}]",
        text,
    )
    return _REMOTE_IMG_HTML.sub("[externes Bild entfernt]", text)
