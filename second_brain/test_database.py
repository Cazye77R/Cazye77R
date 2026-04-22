"""Tests for core/database.py and core/file_watcher.py."""
from __future__ import annotations

import sys
import time
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Patch config to use an in-memory DB before any project import touches disk
from sqlalchemy.pool import StaticPool  # noqa: E402

import core.config as _cfg  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _in_memory_engine():
    """Replace the on-disk SQLite engine with a shared in-memory one for all tests.

    StaticPool ensures every thread (including the watcher's background thread)
    reuses the same underlying connection, so tables created in the main thread
    are visible everywhere.
    """
    mem_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    mem_session = scoped_session(sessionmaker(bind=mem_engine, autoflush=False))
    _cfg.engine = mem_engine
    _cfg.SessionFactory = mem_session

    # Re-patch the already-imported database module
    import core.database as db
    db.engine = mem_engine
    db.SessionFactory = mem_session
    db.Base.metadata.create_all(mem_engine)
    yield
    mem_session.remove()


import core.database as database  # noqa: E402
from core.database import (  # noqa: E402
    delete_note_from_db,
    full_sync,
    get_all_tags,
    get_notes_by_tag,
    get_recent_notes,
    init_db,
    upsert_note,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_note(filename="Note_A.md", title="Note A", tags=None, links=None):
    from datetime import datetime
    return {
        "filename": filename,
        "title": title,
        "content": "Some content.",
        "word_count": 2,
        "tags": tags or ["alpha", "beta"],
        "wikilinks": links or ["Note_B"],
        "created_at": datetime(2026, 4, 22, 9, 0),
        "modified_at": datetime(2026, 4, 22, 9, 0),
    }


@pytest.fixture(autouse=True)
def _clean_db():
    """Wipe all rows between tests and destroy the session.

    Raw DELETEs leave stale expired objects in the identity map.
    SessionFactory.remove() closes and discards the session so the next test
    starts with a clean slate — no phantom objects from previous IDs.
    """
    yield
    session = _cfg.SessionFactory()
    session.execute(database.NoteTag.__table__.delete())
    session.execute(database.Link.__table__.delete())
    session.execute(database.Note.__table__.delete())
    session.execute(database.Tag.__table__.delete())
    session.commit()
    _cfg.SessionFactory.remove()


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_tables_exist_after_init(self):
        init_db()  # idempotent – must not raise
        session = _cfg.SessionFactory()
        # If table didn't exist this would raise
        session.execute(database.Note.__table__.select()).fetchall()


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

class TestUpsertNote:
    def test_inserts_new_note(self):
        upsert_note(_make_note())
        results = get_recent_notes(10)
        assert any(n["filename"] == "Note_A.md" for n in results)

    def test_updates_existing_note(self):
        upsert_note(_make_note())
        updated = _make_note(title="Updated Title")
        upsert_note(updated)
        notes = get_recent_notes(10)
        match = next(n for n in notes if n["filename"] == "Note_A.md")
        assert match["title"] == "Updated Title"

    def test_idempotent_double_upsert(self):
        upsert_note(_make_note())
        upsert_note(_make_note())
        notes = [n for n in get_recent_notes(10) if n["filename"] == "Note_A.md"]
        assert len(notes) == 1

    def test_tags_stored(self):
        upsert_note(_make_note(tags=["x", "y"]))
        tags = dict(get_all_tags())
        assert "x" in tags
        assert "y" in tags

    def test_tags_replaced_on_update(self):
        upsert_note(_make_note(tags=["old"]))
        upsert_note(_make_note(tags=["new"]))
        tags = dict(get_all_tags())
        assert "new" in tags
        assert "old" not in tags

    def test_links_stored(self):
        upsert_note(_make_note(links=["TargetNote"]))
        session = _cfg.SessionFactory()
        from sqlalchemy import select
        links = session.scalars(
            select(database.Link).join(database.Note).where(database.Note.filename == "Note_A.md")
        ).all()
        assert any(lnk.target_name == "TargetNote" for lnk in links)

    def test_links_replaced_on_update(self):
        upsert_note(_make_note(links=["OldTarget"]))
        upsert_note(_make_note(links=["NewTarget"]))
        session = _cfg.SessionFactory()
        from sqlalchemy import select
        links = session.scalars(
            select(database.Link).join(database.Note).where(database.Note.filename == "Note_A.md")
        ).all()
        targets = {lnk.target_name for lnk in links}
        assert "NewTarget" in targets
        assert "OldTarget" not in targets

    def test_dangling_link_allowed(self):
        upsert_note(_make_note(links=["NonExistentNote"]))
        notes = get_recent_notes(10)
        assert any(n["filename"] == "Note_A.md" for n in notes)


# ---------------------------------------------------------------------------
# delete_note_from_db
# ---------------------------------------------------------------------------

class TestDeleteNote:
    def test_deletes_existing(self):
        upsert_note(_make_note())
        assert delete_note_from_db("Note_A.md") is True
        assert not any(n["filename"] == "Note_A.md" for n in get_recent_notes(10))

    def test_returns_false_for_missing(self):
        assert delete_note_from_db("ghost.md") is False

    def test_cascade_removes_links(self):
        upsert_note(_make_note(links=["SomeTarget"]))
        delete_note_from_db("Note_A.md")
        session = _cfg.SessionFactory()
        from sqlalchemy import select
        links = session.scalars(select(database.Link)).all()
        assert links == []


# ---------------------------------------------------------------------------
# get_all_tags
# ---------------------------------------------------------------------------

class TestGetAllTags:
    def test_returns_list_of_tuples(self):
        upsert_note(_make_note(tags=["tagA", "tagB"]))
        tags = get_all_tags()
        assert isinstance(tags, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in tags)

    def test_tag_count_correct(self):
        upsert_note(_make_note("n1.md", tags=["common"]))
        upsert_note(_make_note("n2.md", tags=["common", "unique"]))
        tags = dict(get_all_tags())
        assert tags["common"] == 2
        assert tags["unique"] == 1

    def test_sorted_by_frequency(self):
        upsert_note(_make_note("a.md", tags=["rare"]))
        upsert_note(_make_note("b.md", tags=["popular"]))
        upsert_note(_make_note("c.md", tags=["popular"]))
        tags = get_all_tags()
        counts = [cnt for _, cnt in tags]
        assert counts == sorted(counts, reverse=True)

    def test_empty_when_no_notes(self):
        assert get_all_tags() == []


# ---------------------------------------------------------------------------
# get_notes_by_tag
# ---------------------------------------------------------------------------

class TestGetNotesByTag:
    def test_filters_by_tag(self):
        upsert_note(_make_note("match.md", tags=["target"]))
        upsert_note(_make_note("nomatch.md", tags=["other"]))
        results = get_notes_by_tag("target")
        filenames = [n["filename"] for n in results]
        assert "match.md" in filenames
        assert "nomatch.md" not in filenames

    def test_returns_empty_for_unknown_tag(self):
        assert get_notes_by_tag("nonexistent_tag_xyz") == []

    def test_multiple_notes_with_same_tag(self):
        upsert_note(_make_note("a.md", tags=["shared"]))
        upsert_note(_make_note("b.md", tags=["shared"]))
        results = get_notes_by_tag("shared")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# get_recent_notes
# ---------------------------------------------------------------------------

class TestGetRecentNotes:
    def test_returns_at_most_n(self):
        for i in range(5):
            upsert_note(_make_note(f"note_{i}.md"))
        assert len(get_recent_notes(3)) == 3

    def test_ordered_by_modified_at_desc(self):
        from datetime import datetime
        upsert_note({**_make_note("old.md"), "modified_at": datetime(2026, 1, 1)})
        upsert_note({**_make_note("new.md"), "modified_at": datetime(2026, 4, 22)})
        results = get_recent_notes(10)
        filenames = [n["filename"] for n in results]
        assert filenames.index("new.md") < filenames.index("old.md")

    def test_empty_db_returns_empty(self):
        assert get_recent_notes(10) == []


# ---------------------------------------------------------------------------
# full_sync
# ---------------------------------------------------------------------------

class TestFullSync:
    def test_syncs_vault_files(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "A.md").write_text("---\ntitle: A\ntags: []\n---\nContent A.", encoding="utf-8")
        (vault / "B.md").write_text("---\ntitle: B\ntags: []\n---\nContent B.", encoding="utf-8")
        stats = full_sync(vault)
        assert stats["inserted"] == 2
        assert stats["updated"] == 0

    def test_second_sync_updates(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "C.md").write_text("---\ntitle: C\ntags: []\n---\nHello.", encoding="utf-8")
        full_sync(vault)
        stats = full_sync(vault)
        assert stats["updated"] == 1
        assert stats["inserted"] == 0

    def test_removes_deleted_files(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "Gone.md"
        note.write_text("---\ntitle: Gone\ntags: []\n---\nTemp.", encoding="utf-8")
        full_sync(vault)
        note.unlink()
        stats = full_sync(vault)
        assert stats["deleted"] == 1
        notes = get_recent_notes(10)
        assert not any(n["filename"] == "Gone.md" for n in notes)

    def test_empty_vault_returns_zeros(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        stats = full_sync(vault)
        assert stats == {"inserted": 0, "updated": 0, "deleted": 0}


# ---------------------------------------------------------------------------
# VaultWatcher (integration smoke-test)
# ---------------------------------------------------------------------------

class TestVaultWatcher:
    def test_watcher_starts_and_stops(self, tmp_path):
        from core.file_watcher import VaultWatcher
        vault = tmp_path / "vault"
        vault.mkdir()
        w = VaultWatcher()
        w.start_watching(vault)
        assert w.is_running
        w.stop_watching()
        assert not w.is_running

    def test_watcher_detects_new_file(self, tmp_path):
        from core.file_watcher import VaultWatcher
        vault = tmp_path / "vault"
        vault.mkdir()

        events: list[tuple[str, str]] = []

        def _cb(event_type, filename):
            events.append((event_type, filename))

        w = VaultWatcher()
        w.start_watching(vault, callback=_cb)
        try:
            (vault / "New.md").write_text(
                "---\ntitle: New\ntags: []\n---\nHello watcher.", encoding="utf-8"
            )
            # Wait for debounce + processing (1s debounce + buffer)
            deadline = time.time() + 5
            while not events and time.time() < deadline:
                time.sleep(0.1)
        finally:
            w.stop_watching()

        assert any(e[0] == "upsert" and "New.md" in e[1] for e in events)

    def test_double_start_is_idempotent(self, tmp_path):
        from core.file_watcher import VaultWatcher
        vault = tmp_path / "vault"
        vault.mkdir()
        w = VaultWatcher()
        w.start_watching(vault)
        observer_id = id(w._observer)
        w.start_watching(vault)  # must not create a second observer
        assert id(w._observer) == observer_id
        w.stop_watching()
