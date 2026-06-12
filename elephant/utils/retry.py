import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Ollama is unreachable after all retries."""


def ollama_retry(fn: Callable[[], T], *, retries: int = 3, backoff: float = 2.0, label: str = "") -> T:
    """Call fn(), retrying on any exception with exponential backoff.

    Raises OllamaError when all attempts are exhausted.
    """
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt < retries:
                wait = backoff ** (attempt - 1)
                logger.warning(
                    "Attempt %d/%d failed%s: %s — retrying in %.0fs",
                    attempt, retries, f" ({label})" if label else "", exc, wait,
                )
                time.sleep(wait)
    raise OllamaError(
        f"All {retries} attempts failed{f' ({label})' if label else ''}"
    ) from last
