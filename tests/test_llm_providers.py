"""
StockMind – Tests für llm_providers

Alle Tests laufen offline; Netzwerk-Calls werden gemockt.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    def test_health_true(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp):
            from modules.llm_providers.ollama_provider import OllamaProvider
            assert OllamaProvider().health() is True

    def test_health_false_on_exception(self):
        with patch("requests.get", side_effect=Exception("no conn")):
            from modules.llm_providers.ollama_provider import OllamaProvider
            assert OllamaProvider().health() is False

    def test_get_status_running(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}]}
        with patch("requests.get", return_value=mock_resp):
            from modules.llm_providers.ollama_provider import OllamaProvider
            status = OllamaProvider().get_status()
        assert status["running"] is True
        assert status["model_count"] == 1
        assert status["error"] == ""

    def test_list_models(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "mistral:7b"},
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            from modules.llm_providers.ollama_provider import OllamaProvider
            models = OllamaProvider().list_models()
        assert models == ["llama3", "mistral"]

    def test_list_models_returns_empty_on_error(self):
        with patch("requests.get", side_effect=Exception("err")):
            from modules.llm_providers.ollama_provider import OllamaProvider
            assert OllamaProvider().list_models() == []

    def test_chat_via_http_fallback(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "Hallo"}}
        with patch("requests.post", return_value=mock_resp):
            from modules.llm_providers.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            # Force HTTP path by mocking ImportError for ollama package
            with patch.object(provider, "_chat_via_client", side_effect=ImportError):
                result = provider.chat(
                    [{"role": "user", "content": "Hi"}],
                    model="llama3",
                )
        assert result == "Hallo"

    def test_query_builds_messages(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "Antwort"}}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            from modules.llm_providers.ollama_provider import OllamaProvider
            provider = OllamaProvider()
            with patch.object(provider, "_chat_via_client", side_effect=ImportError):
                result = provider.query("llama3", "Prompt", system_prompt="System")
        assert result == "Antwort"
        payload = mock_post.call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"


# ---------------------------------------------------------------------------
# NvidiaProvider
# ---------------------------------------------------------------------------

class TestNvidiaProvider:
    def test_health_no_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            assert NvidiaProvider().health() is False

    def test_health_invalid_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "not-an-nvapi-key"}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            assert NvidiaProvider().health() is False

    def test_health_valid_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-abc123"}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            assert NvidiaProvider().health() is True

    def test_get_status_no_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            status = NvidiaProvider().get_status()
        assert status["running"] is False
        assert "NVIDIA_API_KEY" in status["error"]

    def test_get_status_valid_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-xyz"}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            status = NvidiaProvider().get_status()
        assert status["running"] is True
        assert status["error"] == ""

    def test_list_models(self):
        with patch.dict(os.environ, {"NVIDIA_MODEL": "meta/llama-3.3-70b-instruct"}, clear=False):
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            models = NvidiaProvider().list_models()
        assert models == ["meta/llama-3.3-70b-instruct"]

    def test_chat_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Analyse-Ergebnis"}}]
        }
        env = {"NVIDIA_API_KEY": "nvapi-test", "NVIDIA_MODEL": "meta/llama-3.3-70b-instruct"}
        with patch.dict(os.environ, env, clear=False):
            with patch("requests.post", return_value=mock_resp):
                from modules.llm_providers.nvidia_provider import NvidiaProvider
                result = NvidiaProvider().chat(
                    [{"role": "user", "content": "Analysiere AAPL"}],
                    model="meta/llama-3.3-70b-instruct",
                )
        assert result == "Analyse-Ergebnis"

    def test_chat_uses_authorization_header(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-secret"}, clear=False):
            with patch("requests.post", return_value=mock_resp) as mock_post:
                from modules.llm_providers.nvidia_provider import NvidiaProvider
                NvidiaProvider().chat([{"role": "user", "content": "Hi"}], model="x")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer nvapi-secret"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_default_is_ollama(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=False):
            from modules.llm_providers.factory import get_provider
            from modules.llm_providers.ollama_provider import OllamaProvider
            assert isinstance(get_provider(), OllamaProvider)

    def test_explicit_nvidia(self):
        from modules.llm_providers.factory import get_provider
        from modules.llm_providers.nvidia_provider import NvidiaProvider
        assert isinstance(get_provider("nvidia"), NvidiaProvider)

    def test_explicit_ollama(self):
        from modules.llm_providers.factory import get_provider
        from modules.llm_providers.ollama_provider import OllamaProvider
        assert isinstance(get_provider("ollama"), OllamaProvider)

    def test_env_nvidia(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "nvidia"}, clear=False):
            from modules.llm_providers.factory import get_provider
            from modules.llm_providers.nvidia_provider import NvidiaProvider
            assert isinstance(get_provider(), NvidiaProvider)

    def test_unknown_defaults_to_ollama(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=False):
            from modules.llm_providers.factory import get_provider
            from modules.llm_providers.ollama_provider import OllamaProvider
            assert isinstance(get_provider(), OllamaProvider)
