import pytest
from pathlib import Path
from unittest.mock import patch

import frontmatter

from elephant.memory.markdown_store import (
    delete_memory,
    list_memories,
    load_memory,
    save_memory,
    search_memories_text,
    update_memory,
)


@pytest.fixture()
def tmp_memories(tmp_path, monkeypatch):
    """Redirect the memories base path to a temp directory."""
    for cat in ("general", "projects", "conversations"):
        (tmp_path / cat).mkdir()

    import elephant.config as cfg_module
    import elephant.memory.markdown_store as store_module

    monkeypatch.setattr(cfg_module.settings, "memory_path", tmp_path)
    monkeypatch.setattr(store_module.settings, "memory_path", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# save_memory
# ---------------------------------------------------------------------------

def test_save_memory_creates_file(tmp_memories):
    path = save_memory("general", "Hello World", "Some content.", ["test"], 0.8)
    assert path.exists()
    assert path.suffix == ".md"


def test_save_memory_frontmatter(tmp_memories):
    save_memory("projects", "My Project", "Project details.", ["python", "ai"], 0.9)
    md_file = next((tmp_memories / "projects").glob("*.md"))
    post = frontmatter.loads(md_file.read_text())
    assert post["title"] == "My Project"
    assert post["tags"] == ["python", "ai"]
    assert post["importance"] == 0.9
    assert "created_at" in post
    assert "updated_at" in post
    assert post.content == "Project details."


def test_save_memory_invalid_category(tmp_memories):
    with pytest.raises(ValueError, match="Unknown category"):
        save_memory("nonexistent", "Title", "Content", [])


def test_save_memory_slug_from_title(tmp_memories):
    path = save_memory("general", "My Cool Memory", "content", [])
    assert path.name == "my_cool_memory.md"


# ---------------------------------------------------------------------------
# load_memory
# ---------------------------------------------------------------------------

def test_load_memory_roundtrip(tmp_memories):
    path = save_memory("general", "Load Test", "Loaded content.", ["load"], 0.6)
    memory = load_memory(path)
    assert memory.metadata.title == "Load Test"
    assert memory.metadata.tags == ["load"]
    assert memory.metadata.importance == 0.6
    assert memory.content == "Loaded content."
    assert memory.category == "general"
    assert memory.filepath == path


def test_load_memory_accepts_string_path(tmp_memories):
    path = save_memory("general", "String Path", "content", [])
    memory = load_memory(str(path))
    assert memory.metadata.title == "String Path"


# ---------------------------------------------------------------------------
# list_memories
# ---------------------------------------------------------------------------

def test_list_memories_all(tmp_memories):
    save_memory("general", "G1", "g1", [])
    save_memory("projects", "P1", "p1", [])
    save_memory("conversations", "C1", "c1", [])
    memories = list_memories()
    assert len(memories) == 3


def test_list_memories_by_category(tmp_memories):
    save_memory("general", "G1", "g1", [])
    save_memory("general", "G2", "g2", [])
    save_memory("projects", "P1", "p1", [])
    memories = list_memories(category="general")
    assert len(memories) == 2
    assert all(m.category == "general" for m in memories)


def test_list_memories_empty(tmp_memories):
    assert list_memories() == []


# ---------------------------------------------------------------------------
# search_memories_text
# ---------------------------------------------------------------------------

def test_search_by_content(tmp_memories):
    save_memory("general", "Python Tips", "Use list comprehensions.", ["python"])
    save_memory("general", "Go Tips", "Use goroutines.", ["go"])
    results = search_memories_text("goroutines")
    assert len(results) == 1
    assert results[0].metadata.title == "Go Tips"


def test_search_by_tag(tmp_memories):
    save_memory("general", "ML Notes", "Some ML content.", ["machine-learning"])
    results = search_memories_text("machine-learning")
    assert len(results) == 1


def test_search_by_title(tmp_memories):
    save_memory("projects", "Elephant Project", "Memory system.", [])
    results = search_memories_text("elephant")
    assert len(results) == 1


def test_search_no_results(tmp_memories):
    save_memory("general", "Cats", "I like cats.", [])
    assert search_memories_text("dogs") == []


def test_search_case_insensitive(tmp_memories):
    save_memory("general", "Python", "Python is great.", [])
    assert len(search_memories_text("PYTHON")) == 1


# ---------------------------------------------------------------------------
# delete_memory
# ---------------------------------------------------------------------------

def test_delete_memory(tmp_memories):
    path = save_memory("general", "To Delete", "bye", [])
    assert path.exists()
    delete_memory(path)
    assert not path.exists()


def test_delete_memory_accepts_string(tmp_memories):
    path = save_memory("general", "To Delete Str", "bye", [])
    delete_memory(str(path))
    assert not path.exists()


# ---------------------------------------------------------------------------
# update_memory
# ---------------------------------------------------------------------------

def test_update_content(tmp_memories):
    path = save_memory("general", "Updatable", "old content", [])
    memory = update_memory(path, content="new content")
    assert memory.content == "new content"
    # Verify file on disk
    assert load_memory(path).content == "new content"


def test_update_tags(tmp_memories):
    path = save_memory("general", "Tag Update", "content", ["old"])
    memory = update_memory(path, tags=["new", "tags"])
    assert memory.metadata.tags == ["new", "tags"]


def test_update_importance(tmp_memories):
    path = save_memory("general", "Importance Update", "content", [], importance=0.3)
    memory = update_memory(path, importance=0.95)
    assert memory.metadata.importance == 0.95


def test_update_sets_updated_at(tmp_memories):
    path = save_memory("general", "Timestamp Test", "content", [])
    original = load_memory(path).metadata.updated_at
    memory = update_memory(path, content="changed")
    assert memory.metadata.updated_at >= original


def test_update_partial_keeps_existing(tmp_memories):
    path = save_memory("general", "Partial", "content", ["keep"], importance=0.7)
    update_memory(path, content="updated only")
    reloaded = load_memory(path)
    assert reloaded.metadata.tags == ["keep"]
    assert reloaded.metadata.importance == 0.7
