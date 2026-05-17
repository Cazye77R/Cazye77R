"""Tests for elephant.utils.retry (ollama_retry + OllamaError)."""

import time
from unittest.mock import MagicMock, call, patch

import pytest

from elephant.utils.retry import OllamaError, ollama_retry


# ---------------------------------------------------------------------------
# Basic success cases
# ---------------------------------------------------------------------------

def test_returns_result_on_first_success():
    fn = MagicMock(return_value=42)
    result = ollama_retry(fn, retries=3)
    assert result == 42
    fn.assert_called_once()


def test_retries_and_succeeds_on_second_attempt():
    fn = MagicMock(side_effect=[RuntimeError("fail"), "ok"])
    with patch("elephant.utils.retry.time.sleep"):
        result = ollama_retry(fn, retries=3)
    assert result == "ok"
    assert fn.call_count == 2


# ---------------------------------------------------------------------------
# Exhaustion → OllamaError
# ---------------------------------------------------------------------------

def test_raises_ollama_error_after_all_retries_fail():
    fn = MagicMock(side_effect=ConnectionError("refused"))
    with patch("elephant.utils.retry.time.sleep"):
        with pytest.raises(OllamaError):
            ollama_retry(fn, retries=3)
    assert fn.call_count == 3


def test_ollama_error_is_raised_not_original_exception():
    fn = MagicMock(side_effect=ValueError("bad"))
    with patch("elephant.utils.retry.time.sleep"):
        with pytest.raises(OllamaError):
            ollama_retry(fn, retries=2)


# ---------------------------------------------------------------------------
# Exponential backoff
# ---------------------------------------------------------------------------

def test_exponential_backoff_sleep_calls():
    fn = MagicMock(side_effect=RuntimeError("fail"))
    with patch("elephant.utils.retry.time.sleep") as mock_sleep:
        with pytest.raises(OllamaError):
            ollama_retry(fn, retries=3, backoff=2.0)
    # backoff^0 = 1.0 for attempt 1, backoff^1 = 2.0 for attempt 2
    # No sleep after the last attempt
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)


# ---------------------------------------------------------------------------
# Label in error message
# ---------------------------------------------------------------------------

def test_label_appears_in_ollama_error_message():
    fn = MagicMock(side_effect=RuntimeError("x"))
    with patch("elephant.utils.retry.time.sleep"):
        with pytest.raises(OllamaError) as exc_info:
            ollama_retry(fn, retries=1, label="my-op")
    assert "my-op" in str(exc_info.value)


def test_no_label_does_not_crash():
    fn = MagicMock(side_effect=RuntimeError("x"))
    with patch("elephant.utils.retry.time.sleep"):
        with pytest.raises(OllamaError) as exc_info:
            ollama_retry(fn, retries=1)
    assert "1 attempts failed" in str(exc_info.value)
