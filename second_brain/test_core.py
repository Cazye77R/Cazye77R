"""Unit tests for core/ vault system."""
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `core` imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.markdown_parser import (
    extract_frontmatter,
    extract_tags,
    extract_wikilinks,
    parse_note,
    render_markdown,
)
from core.vault_manager import VaultManager
from core.graph_engine import NoteGraph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MD = """\
---
title: Testnotiz
created: 2026-04-22 10:00
tags: [python, testing]
---

# Testnotiz

Das ist ein #inline-tag und ein weiterer #test.

Verweis auf [[Andere Notiz]] und [[Dritte|Alias]].

| Spalte A | Spalte B |
|----------|----------|
| 1        | 2        |
"""


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


@pytest.fixture()
def sample_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.md"
    f.write_text(SAMPLE_MD, encoding="utf-8")
    return f


@pytest.fixture()
def populated_vault(tmp_vault: Path) -> VaultManager:
    vm = VaultManager(tmp_vault)
    vm.create_note("Alpha", "Inhalt Alpha. Verweis auf [[Beta]].", tags=["start"])
    vm.create_note("Beta", "Inhalt Beta. Verweis auf [[Alpha]] und [[Gamma]].", tags=["mitte"])
    vm.create_note("Gamma", "Inhalt Gamma. Kein ausgehender Link.", tags=["ende"])
    return vm


# ---------------------------------------------------------------------------
# markdown_parser
# ---------------------------------------------------------------------------

class TestExtractFrontmatter:
    def test_parses_yaml_fields(self, sample_file):
        fm = extract_frontmatter(SAMPLE_MD)
        assert fm["title"] == "Testnotiz"
        assert "python" in fm["tags"]

    def test_returns_empty_on_no_frontmatter(self):
        assert extract_frontmatter("Kein Header hier.") == {}


class TestExtractWikilinks:
    def test_finds_plain_link(self):
        links = extract_wikilinks("Schau dir [[Konzepte]] an.")
        assert "Konzepte" in links

    def test_finds_aliased_link(self):
        links = extract_wikilinks("Lies [[Konzepte|hier]].")
        assert "Konzepte" in links

    def test_multiple_links(self):
        links = extract_wikilinks("[[A]] und [[B|Alias B]] und [[C]]")
        assert links == ["A", "B", "C"]

    def test_no_links(self):
        assert extract_wikilinks("Normaler Text ohne Links.") == []


class TestExtractTags:
    def test_inline_tags(self):
        tags = extract_tags("Ein #python und #testing Beispiel.")
        assert "python" in tags
        assert "testing" in tags

    def test_yaml_tags(self):
        fm = {"tags": ["alpha", "beta"]}
        tags = extract_tags("Kein Inline-Tag.", fm)
        assert "alpha" in tags
        assert "beta" in tags

    def test_deduplication(self):
        fm = {"tags": ["python"]}
        tags = extract_tags("Noch ein #python Verweis.", fm)
        assert tags.count("python") == 1

    def test_yaml_string_tags(self):
        fm = {"tags": "alpha, beta"}
        tags = extract_tags("", fm)
        assert "alpha" in tags
        assert "beta" in tags


class TestRenderMarkdown:
    def test_produces_html(self, sample_file):
        html = render_markdown(SAMPLE_MD)
        assert "<h1" in html or "<p" in html

    def test_wikilinks_become_anchors(self):
        html = render_markdown("Verweis auf [[Konzepte]].")
        assert 'href="/note/Konzepte"' in html

    def test_aliased_wikilink_uses_alias(self):
        html = render_markdown("Lies [[Konzepte|die Grundlagen]].")
        assert "die Grundlagen" in html
        assert 'href="/note/Konzepte"' in html

    def test_table_rendered(self):
        html = render_markdown(SAMPLE_MD)
        assert "<table" in html


class TestParseNote:
    def test_returns_required_keys(self, sample_file):
        note = parse_note(sample_file)
        for key in ("title", "content", "frontmatter", "tags", "wikilinks",
                    "raw_text", "word_count", "created_at", "modified_at"):
            assert key in note, f"Schlüssel fehlt: {key}"

    def test_title_from_frontmatter(self, sample_file):
        assert parse_note(sample_file)["title"] == "Testnotiz"

    def test_wikilinks_extracted(self, sample_file):
        note = parse_note(sample_file)
        assert "Andere Notiz" in note["wikilinks"]
        assert "Dritte" in note["wikilinks"]

    def test_tags_combined(self, sample_file):
        note = parse_note(sample_file)
        assert "python" in note["tags"]
        assert "inline-tag" in note["tags"]

    def test_word_count_positive(self, sample_file):
        assert parse_note(sample_file)["word_count"] > 0

    def test_filename_present(self, sample_file):
        assert parse_note(sample_file)["filename"] == "sample.md"


# ---------------------------------------------------------------------------
# vault_manager
# ---------------------------------------------------------------------------

class TestVaultManager:
    def test_get_all_notes_returns_list(self, populated_vault):
        notes = populated_vault.get_all_notes()
        assert len(notes) == 3

    def test_create_note_file_exists(self, tmp_vault):
        vm = VaultManager(tmp_vault)
        note = vm.create_note("Neue Notiz", "Hallo Welt.", tags=["test"])
        assert Path(note["filepath"]).exists()

    def test_create_note_has_frontmatter(self, tmp_vault):
        vm = VaultManager(tmp_vault)
        note = vm.create_note("FM Test", "Inhalt.", tags=["a", "b"])
        assert note["frontmatter"]["title"] == "FM Test"
        assert "a" in note["frontmatter"]["tags"]

    def test_get_note_by_filename(self, populated_vault):
        notes = populated_vault.get_all_notes()
        filename = notes[0]["filename"]
        fetched = populated_vault.get_note(filename)
        assert fetched is not None
        assert fetched["filename"] == filename

    def test_get_note_missing_returns_none(self, tmp_vault):
        vm = VaultManager(tmp_vault)
        assert vm.get_note("existiert_nicht.md") is None

    def test_update_note_changes_content(self, populated_vault):
        notes = populated_vault.get_all_notes()
        filename = notes[0]["filename"]
        updated = populated_vault.update_note(filename, "Neuer Inhalt hier.")
        assert "Neuer Inhalt hier." in updated["content"]

    def test_update_note_missing_raises(self, tmp_vault):
        vm = VaultManager(tmp_vault)
        with pytest.raises(FileNotFoundError):
            vm.update_note("ghost.md", "Inhalt")

    def test_delete_note(self, populated_vault):
        notes = populated_vault.get_all_notes()
        filename = notes[0]["filename"]
        assert populated_vault.delete_note(filename) is True
        assert populated_vault.get_note(filename) is None

    def test_delete_missing_returns_false(self, tmp_vault):
        vm = VaultManager(tmp_vault)
        assert vm.delete_note("ghost.md") is False

    def test_fulltext_search_finds_match(self, populated_vault):
        results = populated_vault.search_notes_fulltext("Alpha")
        assert len(results) >= 1

    def test_fulltext_search_case_insensitive(self, populated_vault):
        results = populated_vault.search_notes_fulltext("inhalt alpha")
        assert len(results) >= 1

    def test_fulltext_search_no_match(self, populated_vault):
        assert populated_vault.search_notes_fulltext("xyzzy_keine_treffer") == []

    def test_get_backlinks(self, populated_vault):
        # Beta links to Alpha → Alpha should have Beta as backlink
        backlinks = populated_vault.get_backlinks("Alpha.md")
        filenames = [b["filename"] for b in backlinks]
        assert any("Beta" in f for f in filenames)

    def test_get_stats_keys(self, populated_vault):
        stats = populated_vault.get_stats()
        for key in ("total_notes", "total_words", "total_tags", "total_links"):
            assert key in stats

    def test_get_stats_counts(self, populated_vault):
        stats = populated_vault.get_stats()
        assert stats["total_notes"] == 3
        assert stats["total_words"] > 0
        assert stats["total_links"] > 0


# ---------------------------------------------------------------------------
# graph_engine
# ---------------------------------------------------------------------------

class TestNoteGraph:
    @pytest.fixture()
    def graph_with_notes(self, populated_vault) -> NoteGraph:
        ng = NoteGraph()
        ng.build_graph(populated_vault.get_all_notes())
        return ng

    def test_build_graph_has_nodes(self, graph_with_notes):
        assert len(graph_with_notes.graph.nodes) >= 3

    def test_build_graph_has_edges(self, graph_with_notes):
        assert len(graph_with_notes.graph.edges) > 0

    def test_get_neighbors_outgoing(self, graph_with_notes):
        neighbors = graph_with_notes.get_neighbors("Alpha")
        assert "Beta" in neighbors["outgoing"]

    def test_get_neighbors_incoming(self, graph_with_notes):
        neighbors = graph_with_notes.get_neighbors("Beta")
        assert "Alpha" in neighbors["incoming"]

    def test_get_neighbors_unknown_node(self, graph_with_notes):
        result = graph_with_notes.get_neighbors("Existiert_Nicht")
        assert result == {"outgoing": [], "incoming": []}

    def test_get_most_connected_length(self, graph_with_notes):
        top = graph_with_notes.get_most_connected(n=2)
        assert len(top) <= 2

    def test_get_most_connected_sorted(self, graph_with_notes):
        top = graph_with_notes.get_most_connected(n=10)
        degrees = [d for _, d in top]
        assert degrees == sorted(degrees, reverse=True)

    def test_get_orphans_empty_graph(self):
        ng = NoteGraph()
        ng.build_graph([])
        assert ng.get_orphans() == []

    def test_export_pyvis_creates_file(self, graph_with_notes, tmp_path):
        out = tmp_path / "graph.html"
        result = graph_with_notes.export_pyvis(out)
        assert result.exists()
        assert result.suffix == ".html"
