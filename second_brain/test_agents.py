"""Tests for ai/note_assistant, ai/briefing_agent, plugins/smart_search, plugins/link_suggester."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai.note_assistant import NoteAssistant, _parse_json_list
from ai.briefing_agent import BriefingAgent
from ai.ollama_client import OllamaClient, OllamaConnectionError
from plugins.smart_search import SmartSearch, SearchResult
from plugins.link_suggester import LinkSuggester, _Cache


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _note(
    filename: str = "Test.md",
    title: str = "Test",
    content: str = "Testinhalt",
    tags: list[str] | None = None,
    wikilinks: list[str] | None = None,
    modified_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "title": title,
        "content": content,
        "word_count": len(content.split()),
        "tags": tags or ["test"],
        "wikilinks": wikilinks or [],
        "created_at": datetime(2026, 4, 22),
        "modified_at": modified_at or datetime(2026, 4, 22),
        "raw_text": content,
        "frontmatter": {},
        "filepath": f"/vault/{filename}",
    }


@pytest.fixture()
def mock_ollama() -> MagicMock:
    client = MagicMock(spec=OllamaClient)
    client.chat.return_value = '["ki", "python", "lernen"]'
    client.is_available.return_value = True
    return client


@pytest.fixture()
def mock_rag() -> MagicMock:
    rag = MagicMock()
    rag.search_semantic.return_value = [
        {"filename": "A.md", "title": "Alpha", "excerpt": "...", "score": 0.9},
        {"filename": "B.md", "title": "Beta", "excerpt": "...", "score": 0.7},
    ]
    rag.search_hybrid.return_value = [
        {"filename": "A.md", "title": "Alpha", "excerpt": "...", "score": 0.9},
    ]
    rag.find_related_notes.return_value = [
        {"filename": "C.md", "title": "Gamma", "excerpt": "...", "score": 0.8},
    ]
    return rag


@pytest.fixture()
def mock_vault() -> MagicMock:
    vm = MagicMock()
    vm.get_all_notes.return_value = [
        _note("A.md", "Alpha"),
        _note("B.md", "Beta"),
        _note("C.md", "Gamma"),
    ]
    vm.get_note.side_effect = lambda fn: _note(fn, fn.removesuffix(".md"))
    vm.search_notes_fulltext.return_value = [_note("A.md", "Alpha", "Treffer gefunden")]
    vm.get_stats.return_value = {
        "total_notes": 3,
        "total_words": 100,
        "total_tags": 5,
        "total_links": 4,
    }
    return vm


# ===========================================================================
# _parse_json_list
# ===========================================================================

class TestParseJsonList:
    def test_parses_clean_list(self):
        assert _parse_json_list('["a", "b", "c"]') == ["a", "b", "c"]

    def test_parses_embedded_list(self):
        result = _parse_json_list('Hier sind Tags: ["ki", "lernen"] – Ende.')
        assert result == ["ki", "lernen"]

    def test_returns_empty_on_garbage(self):
        assert _parse_json_list("kein json hier") == []

    def test_parses_dict_list(self):
        raw = '[{"filename": "A.md", "confidence": 0.9}]'
        result = _parse_json_list(raw)
        assert result[0]["filename"] == "A.md"

    def test_handles_empty_list(self):
        assert _parse_json_list("[]") == []


# ===========================================================================
# NoteAssistant – suggest_tags
# ===========================================================================

class TestSuggestTags:
    def test_returns_list_of_strings(self, mock_ollama, mock_rag):
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        tags = assistant.suggest_tags("KI-Notiz über Python-Programmierung")
        assert isinstance(tags, list)
        assert all(isinstance(t, str) for t in tags)

    def test_parses_json_from_llm(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = '["ki", "python", "lernen"]'
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        tags = assistant.suggest_tags("Notiz")
        assert "ki" in tags

    def test_max_7_tags(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = json.dumps([f"tag{i}" for i in range(15)])
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        tags = assistant.suggest_tags("x")
        assert len(tags) <= 7

    def test_tags_are_lowercase(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = '["Python", "KI", "Lernen"]'
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        tags = assistant.suggest_tags("x")
        assert all(t == t.lower() for t in tags)

    def test_fallback_on_connection_error(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        tags = assistant.suggest_tags("Text mit #python und #ki-tag")
        assert isinstance(tags, list)

    def test_fallback_extracts_inline_tags(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        tags = assistant.suggest_tags("Notiz über #python und #machine-learning")
        assert "python" in tags
        assert "machine-learning" in tags

    def test_handles_malformed_json(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = "Ich schlage vor: python, ki"
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        tags = assistant.suggest_tags("Notiz")
        assert isinstance(tags, list)  # must not raise


# ===========================================================================
# NoteAssistant – suggest_links
# ===========================================================================

class TestSuggestLinks:
    def _valid_link_response(self) -> str:
        return json.dumps([
            {"filename": "A.md", "title": "Alpha", "reason": "Thema überschneidet sich", "confidence": 0.85},
        ])

    def test_returns_list_of_dicts(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = self._valid_link_response()
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        links = assistant.suggest_links("Notizinhalt", ["Alpha", "Beta"])
        assert isinstance(links, list)
        assert all(isinstance(l, dict) for l in links)

    def test_result_has_required_keys(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = self._valid_link_response()
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        links = assistant.suggest_links("Notiz", ["Alpha"])
        for key in ("filename", "title", "reason", "confidence"):
            assert key in links[0]

    def test_falls_back_to_semantic_on_bad_json(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = "kein json"
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        links = assistant.suggest_links("Notiz", ["Alpha", "Beta"])
        assert len(links) > 0  # semantic fallback kicks in

    def test_fallback_on_connection_error(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        mock_rag.search_semantic.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        links = assistant.suggest_links("Notiz", ["Alpha", "Beta", "Gamma"])
        assert isinstance(links, list)
        assert len(links) <= 3

    def test_max_5_results(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = json.dumps(
            [{"filename": f"{i}.md", "title": str(i), "reason": "x", "confidence": 0.5}
             for i in range(10)]
        )
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        links = assistant.suggest_links("Notiz", [str(i) for i in range(10)])
        assert len(links) <= 5


# ===========================================================================
# NoteAssistant – structure_note
# ===========================================================================

class TestStructureNote:
    def test_returns_string(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = "# Titel\n\nInhalt"
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        result = assistant.structure_note("roher text")
        assert isinstance(result, str)

    def test_fallback_creates_heading(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        result = assistant.structure_note("Mein erster Satz.\nZweiter Satz.")
        assert result.startswith("#")

    def test_fallback_preserves_content(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        result = assistant.structure_note("Wichtiger Inhalt hier.")
        assert "Wichtiger Inhalt hier." in result


# ===========================================================================
# NoteAssistant – expand_note
# ===========================================================================

class TestExpandNote:
    def test_returns_string(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = "## Ergänzungen\n- Idee 1\n- Idee 2"
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        result = assistant.expand_note(_note())
        assert isinstance(result, str)

    def test_fallback_returns_template(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        result = assistant.expand_note(_note(title="Meine Notiz"))
        assert "Meine Notiz" in result
        assert len(result) > 20

    def test_passes_title_in_prompt(self, mock_ollama, mock_rag):
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        assistant.expand_note(_note(title="Sondertitel"))
        call_content = mock_ollama.chat.call_args.args[0][0]["content"]
        assert "Sondertitel" in call_content


# ===========================================================================
# NoteAssistant – extract_action_items
# ===========================================================================

class TestExtractActionItems:
    def test_returns_list(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = '["Aufgabe 1", "Aufgabe 2"]'
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        items = assistant.extract_action_items("Notizinhalt")
        assert isinstance(items, list)

    def test_parses_json(self, mock_ollama, mock_rag):
        mock_ollama.chat.return_value = '["Bericht schreiben", "Meeting planen"]'
        assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
        items = assistant.extract_action_items("x")
        assert "Bericht schreiben" in items

    def test_fallback_finds_checkboxes(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        content = "- [ ] Aufgabe A\n- [x] Erledigt\n- [ ] Aufgabe B"
        items = assistant.extract_action_items(content)
        assert any("Aufgabe A" in i for i in items)
        assert any("Aufgabe B" in i for i in items)

    def test_fallback_finds_todo_prefix(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        content = "TODO: Dokumentation fertigstellen\nNormaler Text"
        items = assistant.extract_action_items(content)
        assert any("Dokumentation" in i for i in items)

    def test_fallback_deduplicates(self, mock_rag):
        client = MagicMock(spec=OllamaClient)
        client.chat.side_effect = OllamaConnectionError("down")
        assistant = NoteAssistant(ollama=client, rag=mock_rag)
        content = "- [ ] Doppelt\n- [ ] Doppelt"
        items = assistant.extract_action_items(content)
        assert items.count("Doppelt") <= 1


# ===========================================================================
# BriefingAgent
# ===========================================================================

class TestBriefingAgent:
    @pytest.fixture()
    def agent(self, mock_ollama, mock_rag, mock_vault, tmp_path) -> BriefingAgent:
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            agent = BriefingAgent.__new__(BriefingAgent)
            agent._ollama = mock_ollama
            agent._rag = mock_rag
            agent._vault = mock_vault
            from ai.note_assistant import NoteAssistant
            agent._assistant = NoteAssistant(ollama=mock_ollama, rag=mock_rag)
            yield agent

    def test_returns_required_keys(self, agent, mock_vault, tmp_path):
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[
                {**_note("A.md"), "modified_at": datetime.utcnow()}
            ]):
                briefing = agent.generate_daily_briefing()
        for key in ("date", "summary", "recent_notes", "suggested_connections", "open_todos", "stats", "insight"):
            assert key in briefing

    def test_date_is_today(self, agent, tmp_path):
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[]):
                briefing = agent.generate_daily_briefing()
        from datetime import date
        assert briefing["date"] == date.today().strftime("%Y-%m-%d")

    def test_saves_markdown_file(self, agent, tmp_path):
        briefings_dir = tmp_path / "briefings"
        with patch("ai.briefing_agent._BRIEFINGS_DIR", briefings_dir):
            with patch("core.database.get_recent_notes", return_value=[]):
                briefing = agent.generate_daily_briefing()
        saved = list(briefings_dir.glob("*.md"))
        assert len(saved) == 1

    def test_insight_fallback_on_connection_error(self, agent, tmp_path):
        agent._ollama.chat.side_effect = OllamaConnectionError("down")
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[
                {**_note("A.md"), "modified_at": datetime.utcnow()}
            ]):
                briefing = agent.generate_daily_briefing()
        assert isinstance(briefing["insight"], str)
        assert len(briefing["insight"]) > 0

    def test_empty_vault_still_works(self, agent, mock_vault, tmp_path):
        mock_vault.get_all_notes.return_value = []
        mock_vault.get_stats.return_value = {"total_notes": 0, "total_words": 0, "total_tags": 0, "total_links": 0}
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[]):
                briefing = agent.generate_daily_briefing()
        assert briefing["recent_notes"] == []

    def test_recent_notes_filtered_by_7_days(self, agent, tmp_path):
        old_note = {**_note("Old.md"), "modified_at": datetime.utcnow() - timedelta(days=10)}
        new_note = {**_note("New.md"), "modified_at": datetime.utcnow() - timedelta(days=1)}
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[old_note, new_note]):
                briefing = agent.generate_daily_briefing()
        filenames = [n["filename"] for n in briefing["recent_notes"]]
        assert "New.md" in filenames
        assert "Old.md" not in filenames

    def test_open_todos_is_list(self, agent, tmp_path):
        agent._ollama.chat.return_value = '["TODO 1", "TODO 2"]'
        with patch("ai.briefing_agent._BRIEFINGS_DIR", tmp_path / "briefings"):
            with patch("core.database.get_recent_notes", return_value=[
                {**_note("A.md"), "modified_at": datetime.utcnow()}
            ]):
                briefing = agent.generate_daily_briefing()
        assert isinstance(briefing["open_todos"], list)


# ===========================================================================
# SmartSearch
# ===========================================================================

class TestSmartSearch:
    @pytest.fixture()
    def search(self, mock_rag, mock_vault) -> SmartSearch:
        s = SmartSearch.__new__(SmartSearch)
        s._rag = mock_rag
        s._vault = mock_vault
        return s

    def test_search_returns_list(self, search):
        results = search.search("test")
        assert isinstance(results, list)

    def test_search_returns_search_results(self, search):
        results = search.search("test")
        assert all(isinstance(r, SearchResult) for r in results)

    def test_semantic_mode(self, search):
        results = search.search("test", mode="semantic")
        assert all(r.match_type == "semantic" for r in results)

    def test_fulltext_mode(self, search):
        results = search.search("test", mode="fulltext")
        assert all(r.match_type == "fulltext" for r in results)

    def test_tag_mode_filters_by_tag(self, search, mock_vault):
        mock_vault.get_all_notes.return_value = [
            _note("A.md", tags=["python"]),
            _note("B.md", tags=["ki"]),
        ]
        results = search.search("python", mode="tag")
        assert all(r.match_type == "tag" for r in results)
        assert all("python" in r.tags for r in results)

    def test_tag_mode_partial_match(self, search, mock_vault):
        mock_vault.get_all_notes.return_value = [
            _note("A.md", tags=["python-basics"]),
        ]
        results = search.search("python", mode="tag")
        assert len(results) == 1

    def test_hybrid_mode(self, search):
        results = search.search("test", mode="hybrid")
        assert all(r.match_type == "hybrid" for r in results)

    def test_unknown_mode_defaults_to_hybrid(self, search):
        results = search.search("test", mode="invalid_mode")
        assert all(r.match_type == "hybrid" for r in results)

    def test_semantic_fallback_on_connection_error(self, search, mock_rag, mock_vault):
        mock_rag.search_semantic.side_effect = OllamaConnectionError("down")
        results = search.search("Treffer", mode="semantic")
        assert all(r.match_type == "fulltext" for r in results)

    def test_hybrid_fallback_on_connection_error(self, search, mock_rag):
        mock_rag.search_hybrid.side_effect = OllamaConnectionError("down")
        results = search.search("Treffer", mode="hybrid")
        assert all(r.match_type == "fulltext" for r in results)

    def test_result_score_between_0_and_1(self, search):
        results = search.search("test")
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_result_has_tags(self, search):
        results = search.search("test", mode="semantic")
        for r in results:
            assert isinstance(r.tags, list)


class TestHighlightMatches:
    @pytest.fixture()
    def search(self, mock_rag, mock_vault) -> SmartSearch:
        s = SmartSearch.__new__(SmartSearch)
        s._rag = mock_rag
        s._vault = mock_vault
        return s

    def test_bolds_matching_terms(self, search):
        result = search.highlight_matches("Python ist toll", "python")
        assert "**Python**" in result or "**python**" in result.lower()

    def test_case_insensitive(self, search):
        result = search.highlight_matches("PYTHON ist toll", "python")
        assert "**" in result

    def test_no_match_returns_unchanged(self, search):
        text = "Kein Treffer hier"
        result = search.highlight_matches(text, "xyz")
        assert result == text

    def test_short_query_terms_ignored(self, search):
        # Single-char terms are below the >= 2 threshold and must not be highlighted
        result = search.highlight_matches("ein kurzer Text", "a")
        assert "**" not in result

    def test_multiple_terms(self, search):
        result = search.highlight_matches("Python und KI sind toll", "python ki")
        assert result.count("**") >= 4  # both words wrapped


# ===========================================================================
# _Cache (TTL)
# ===========================================================================

class TestCache:
    def test_get_returns_none_on_miss(self):
        cache = _Cache()
        assert cache.get("missing") is None

    def test_set_and_get(self):
        cache = _Cache()
        cache.set("k", [{"a": 1}])
        result = cache.get("k")
        assert result == [{"a": 1}]

    def test_ttl_expiry(self):
        cache = _Cache(ttl=0.05)
        cache.set("k", [{"a": 1}])
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_invalidate_single_key(self):
        cache = _Cache()
        cache.set("a", [])
        cache.set("b", [])
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") is not None

    def test_clear_all(self):
        cache = _Cache()
        cache.set("a", [])
        cache.set("b", [])
        cache.clear()
        assert len(cache) == 0

    def test_len(self):
        cache = _Cache()
        assert len(cache) == 0
        cache.set("a", [])
        assert len(cache) == 1


# ===========================================================================
# LinkSuggester
# ===========================================================================

class TestLinkSuggester:
    @pytest.fixture()
    def suggester(self, mock_rag, mock_vault) -> LinkSuggester:
        from core.graph_engine import NoteGraph
        graph = MagicMock(spec=NoteGraph)
        graph.get_orphans.return_value = ["Orphan"]
        graph.build_graph.return_value = None
        ls = LinkSuggester.__new__(LinkSuggester)
        ls._rag = mock_rag
        ls._vault = mock_vault
        ls._graph = graph
        ls._cache = _Cache(ttl=3600)
        return ls

    def test_returns_list(self, suggester):
        result = suggester.get_suggestions_for_note("A.md")
        assert isinstance(result, list)

    def test_result_has_required_keys(self, suggester):
        result = suggester.get_suggestions_for_note("A.md")
        if result:
            for key in ("filename", "title", "score", "already_linked"):
                assert key in result[0]

    def test_excludes_self(self, suggester, mock_rag):
        mock_rag.find_related_notes.return_value = [
            {"filename": "A.md", "title": "Alpha", "excerpt": "...", "score": 0.9},
            {"filename": "B.md", "title": "Beta", "excerpt": "...", "score": 0.7},
        ]
        result = suggester.get_suggestions_for_note("A.md")
        filenames = [r["filename"] for r in result]
        assert "A.md" not in filenames

    def test_cache_hit(self, suggester):
        suggester.get_suggestions_for_note("A.md")
        suggester.get_suggestions_for_note("A.md")
        assert suggester._rag.find_related_notes.call_count == 1

    def test_cache_miss_after_invalidate(self, suggester):
        suggester.get_suggestions_for_note("A.md")
        suggester.invalidate_cache("A.md")
        suggester.get_suggestions_for_note("A.md")
        assert suggester._rag.find_related_notes.call_count == 2

    def test_returns_empty_for_unknown_note(self, suggester, mock_vault):
        mock_vault.get_note.side_effect = None   # clear side_effect so return_value takes effect
        mock_vault.get_note.return_value = None
        result = suggester.get_suggestions_for_note("nonexistent.md")
        assert result == []

    def test_already_linked_flag(self, suggester, mock_vault, mock_rag):
        mock_vault.get_note.side_effect = lambda fn: _note(
            fn, fn.removesuffix(".md"), wikilinks=["C"]
        )
        mock_rag.find_related_notes.return_value = [
            {"filename": "C.md", "title": "Gamma", "excerpt": "...", "score": 0.8},
        ]
        result = suggester.get_suggestions_for_note("A.md")
        if result:
            linked = {r["filename"]: r["already_linked"] for r in result}
            assert linked.get("C.md") is True

    def test_get_orphan_suggestions_returns_list(self, suggester):
        result = suggester.get_orphan_suggestions()
        assert isinstance(result, list)

    def test_orphan_suggestions_structure(self, suggester):
        result = suggester.get_orphan_suggestions()
        for item in result:
            assert "orphan" in item
            assert "suggestions" in item

    def test_fallback_on_rag_error(self, suggester, mock_rag, mock_vault):
        mock_rag.find_related_notes.side_effect = Exception("chromadb down")
        result = suggester.get_suggestions_for_note("A.md")
        assert isinstance(result, list)

    def test_invalidate_all_clears_cache(self, suggester):
        suggester.get_suggestions_for_note("A.md")
        suggester.get_suggestions_for_note("B.md")
        suggester.invalidate_cache()
        assert len(suggester._cache) == 0
