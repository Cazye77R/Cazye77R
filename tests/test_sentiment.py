"""
StockMind – Tests für sentiment_analyzer und explainer.

Alle LLM-Aufrufe werden mit MagicMock gemockt.
yfinance-Aufrufe werden durch monkeypatching ersetzt.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))

from modules.sentiment_analyzer import _parse_response, _fetch_headlines, analyze_news
from modules.explainer import (
    _top_features, _fmt_value, _sentiment_label, _fallback_explanation,
    explain_decision,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _mock_provider(response: str = "0.5") -> MagicMock:
    """Erstellt einen gemockten LLMProvider."""
    prov = MagicMock()
    prov.list_models.return_value = ["test-model"]
    prov.query.return_value = response
    return prov


def _mock_yfinance_news(titles: list[str]):
    """Gibt yfinance-News im neueren Content-Format zurück."""
    return [{"content": {"title": t}} for t in titles]


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_single_score(self):
        assert _parse_response("0.5", 1) == [0.5]

    def test_negative_score(self):
        assert _parse_response("-0.8", 1) == [-0.8]

    def test_multiple_scores(self):
        result = _parse_response("0.3, -0.7, 0.2", 3)
        assert len(result) == 3
        assert abs(result[0] - 0.3) < 0.001
        assert abs(result[1] - (-0.7)) < 0.001
        assert abs(result[2] - 0.2) < 0.001

    def test_clamps_to_minus_one(self):
        result = _parse_response("-2.5", 1)
        assert result[0] == -1.0

    def test_clamps_to_plus_one(self):
        result = _parse_response("3.0", 1)
        assert result[0] == 1.0

    def test_missing_scores_padded_with_none(self):
        result = _parse_response("0.4", 3)
        assert result[0] == 0.4
        assert result[1] is None
        assert result[2] is None

    def test_noisy_response_extracts_numbers(self):
        result = _parse_response("Analyse: Bewertung 0.6 für die Headline.", 1)
        assert result[0] == 0.6

    def test_empty_response(self):
        result = _parse_response("", 2)
        assert result == [None, None]

    def test_integer_score(self):
        result = _parse_response("1", 1)
        assert result[0] == 1.0

    def test_scores_truncated_to_expected(self):
        result = _parse_response("0.1, 0.2, 0.3, 0.4, 0.5", 2)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _fetch_headlines
# ---------------------------------------------------------------------------

class TestFetchHeadlines:
    def test_new_format_content_title(self):
        news = [{"content": {"title": f"Headline {i}"}} for i in range(7)]
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = news
            result = _fetch_headlines("AAPL", 5)
        assert len(result) == 5
        assert result[0] == "Headline 0"

    def test_old_format_title_key(self):
        news = [{"title": f"Alt-Headline {i}"} for i in range(3)]
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = news
            result = _fetch_headlines("MSFT", 5)
        assert len(result) == 3

    def test_empty_news_returns_empty_list(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = []
            result = _fetch_headlines("TSLA", 5)
        assert result == []

    def test_yfinance_exception_returns_empty(self):
        with patch("yfinance.Ticker", side_effect=Exception("network")):
            result = _fetch_headlines("GOOG", 5)
        assert result == []

    def test_skips_empty_titles(self):
        news = [
            {"content": {"title": "Good Headline"}},
            {"content": {"title": ""}},
            {"title": None},
            {"content": {"title": "Another Headline"}},
        ]
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = news
            result = _fetch_headlines("AMZN", 5)
        assert result == ["Good Headline", "Another Headline"]


# ---------------------------------------------------------------------------
# analyze_news
# ---------------------------------------------------------------------------

class TestAnalyzeNews:
    def test_positive_sentiment(self):
        headlines = ["Apple beats earnings expectations"]
        prov = _mock_provider("0.8")
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(headlines)
            result = analyze_news("AAPL", n=1, provider=prov, model_name="llama3")
        assert result["score"] == 0.8
        assert result["n_news"] == 1
        assert result["error"] == ""

    def test_negative_sentiment(self):
        headlines = ["Company faces major fraud allegations"]
        prov = _mock_provider("-0.9")
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(headlines)
            result = analyze_news("FRAUD", n=1, provider=prov, model_name="m")
        assert result["score"] == -0.9

    def test_multiple_headlines_averaged(self):
        # 3 headlines → provider returns "0.6, -0.2, 0.4" → mean = 0.267
        headlines = [f"Headline {i}" for i in range(3)]
        prov = _mock_provider("0.6, -0.2, 0.4")
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(headlines)
            result = analyze_news("TICK", n=3, provider=prov, model_name="m")
        assert result["n_news"] == 3
        expected_avg = (0.6 + (-0.2) + 0.4) / 3
        assert abs(result["score"] - expected_avg) < 0.01

    def test_no_news_returns_neutral(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = []
            result = analyze_news("NONE", provider=_mock_provider())
        assert result["score"] == 0.0
        assert result["n_news"] == 0

    def test_samples_structure(self):
        headlines = ["Good news", "Bad news"]
        prov = _mock_provider("0.5, -0.5")
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(headlines)
            result = analyze_news("TEST", n=2, provider=prov, model_name="m")
        assert len(result["samples"]) == 2
        assert "title" in result["samples"][0]
        assert "score" in result["samples"][0]

    def test_llm_exception_returns_error(self):
        prov = _mock_provider()
        prov.query.side_effect = ConnectionError("LLM offline")
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(["Some headline"])
            result = analyze_news("FAIL", n=1, provider=prov, model_name="m")
        assert result["score"] == 0.0
        assert result["error"] != ""

    def test_score_clamped_to_range(self):
        prov = _mock_provider("1.5")  # LLM halluziniert außerhalb Bereich
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(["Extreme headline"])
            result = analyze_news("XTREME", n=1, provider=prov, model_name="m")
        assert result["score"] <= 1.0

    def test_auto_selects_first_model(self):
        """Wenn model_name leer, wird provider.list_models()[0] genutzt."""
        prov = _mock_provider("0.3")
        prov.list_models.return_value = ["auto-model"]
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.news = _mock_yfinance_news(["headline"])
            analyze_news("AUTO", n=1, provider=prov, model_name="")
        # query muss mit model="auto-model" aufgerufen worden sein
        call_kwargs = prov.query.call_args
        assert call_kwargs.kwargs.get("model") == "auto-model"


# ---------------------------------------------------------------------------
# explainer – Hilfsfunktionen
# ---------------------------------------------------------------------------

class TestExplainerHelpers:
    def test_top_features_sorted_by_importance(self):
        features = {"rsi": 28.0, "macd_hist": 0.5, "ret_1d": -0.01, "bb_pos": -0.3}
        importances = {"rsi": 0.4, "macd_hist": 0.3, "ret_1d": 0.2, "bb_pos": 0.1}
        top = _top_features(features, importances, n=2)
        assert top[0][0] == "rsi"      # höchste Importance
        assert top[1][0] == "macd_hist"

    def test_top_features_respects_n(self):
        features = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
        importances = {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}
        top = _top_features(features, importances, n=2)
        assert len(top) == 2

    def test_top_features_skips_missing_keys(self):
        features = {"rsi": 30.0}
        importances = {"rsi": 0.6, "macd_hist": 0.4}  # macd_hist nicht in features
        top = _top_features(features, importances, n=3)
        assert len(top) == 1

    def test_fmt_value_rsi(self):
        assert "28.0" in _fmt_value("rsi", 28.0)

    def test_fmt_value_return_percent(self):
        val = _fmt_value("ret_1d", 0.025)
        assert "%" in val

    def test_fmt_value_sentiment(self):
        val = _fmt_value("sentiment", 0.5)
        assert "+" in val

    def test_sentiment_label_ranges(self):
        assert _sentiment_label(0.8) == "sehr positiv"
        assert _sentiment_label(0.3) == "positiv"
        assert _sentiment_label(0.0) == "neutral"
        assert _sentiment_label(-0.3) == "negativ"
        assert _sentiment_label(-0.8) == "sehr negativ"

    def test_fallback_explanation_no_top(self):
        result = _fallback_explanation("KAUFEN", 0.5, [])
        assert "KAUFEN" in result
        assert "0.50" in result

    def test_fallback_explanation_with_top(self):
        top3 = [("rsi", 28.0, 0.4)]
        result = _fallback_explanation("KAUFEN", 0.3, top3)
        assert "KAUFEN" in result
        assert "RSI" in result or "rsi" in result.lower()


# ---------------------------------------------------------------------------
# explain_decision (mit gemocktem Provider)
# ---------------------------------------------------------------------------

class TestExplainDecision:
    def _features_and_importances(self):
        features = {"rsi": 28.0, "macd_hist": 0.5, "ret_1d": -0.01, "bb_pos": -0.3}
        importances = {"rsi": 0.4, "macd_hist": 0.3, "ret_1d": 0.2, "bb_pos": 0.1}
        return features, importances

    def test_returns_llm_response(self):
        prov = _mock_provider("Das Modell empfiehlt Kauf wegen überverkauftem RSI.")
        feats, imps = self._features_and_importances()
        result = explain_decision(feats, "KAUFEN", 0.5, imps, provider=prov)
        assert "RSI" in result or "empfiehlt" in result

    def test_llm_called_with_german_signal(self):
        prov = _mock_provider("Erklärung.")
        feats, imps = self._features_and_importances()
        explain_decision(feats, "KAUFEN", 0.3, imps, provider=prov, model_name="llama3")
        prompt_arg = prov.query.call_args.kwargs.get("prompt", "")
        assert "Kauf-Signal" in prompt_arg

    def test_llm_error_returns_fallback(self):
        prov = _mock_provider()
        prov.query.side_effect = ConnectionError("offline")
        feats, imps = self._features_and_importances()
        result = explain_decision(feats, "HALTEN", 0.0, imps, provider=prov)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_importances_uses_fallback(self):
        prov = _mock_provider("OK")
        result = explain_decision({"rsi": 30.0}, "HALTEN", 0.0, {}, provider=prov)
        assert isinstance(result, str)

    def test_auto_selects_first_model(self):
        prov = _mock_provider("Erklärung")
        prov.list_models.return_value = ["best-model"]
        feats, imps = self._features_and_importances()
        explain_decision(feats, "KAUFEN", 0.2, imps, provider=prov, model_name="")
        call_kwargs = prov.query.call_args.kwargs
        assert call_kwargs.get("model") == "best-model"
