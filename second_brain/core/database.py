"""SQLite persistence layer via SQLAlchemy 2.x."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.config import engine, SessionFactory
from core.markdown_parser import parse_note


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="note_tags", back_populates="notes"
    )
    links: Mapped[list[Link]] = relationship(
        "Link", back_populates="source", cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    notes: Mapped[list[Note]] = relationship(
        "Note", secondary="note_tags", back_populates="tags"
    )


class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Target is stored as a raw name; the target note may not exist yet.
    target_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    source: Mapped[Note] = relationship("Note", back_populates="links")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    Base.metadata.create_all(engine)


def upsert_note(note_dict: dict[str, Any]) -> None:
    session = SessionFactory()
    try:
        filename = note_dict["filename"]
        now = datetime.utcnow()

        note = session.scalars(select(Note).where(Note.filename == filename)).first()
        if note is None:
            note = Note(filename=filename)
            session.add(note)

        note.title = note_dict.get("title") or filename
        note.content = note_dict.get("content", "")
        note.word_count = note_dict.get("word_count", 0)
        note.created_at = note_dict.get("created_at") or now
        note.modified_at = note_dict.get("modified_at") or now
        note.indexed_at = now

        # Flush once to obtain note.id before writing associations
        session.flush()

        # --- Tags: replace strategy ---
        note.tags.clear()
        for tag_name in note_dict.get("tags", []):
            tag = session.scalars(select(Tag).where(Tag.name == tag_name)).first()
            if tag is None:
                tag = Tag(name=tag_name)
                session.add(tag)
            note.tags.append(tag)

        # --- Links: replace strategy ---
        session.execute(delete(Link).where(Link.source_id == note.id))
        for target in note_dict.get("wikilinks", []):
            session.add(Link(source_id=note.id, target_name=target))

        session.commit()
    except Exception:
        session.rollback()
        raise


def delete_note_from_db(filename: str) -> bool:
    session = SessionFactory()
    try:
        note = session.scalars(select(Note).where(Note.filename == filename)).first()
        if note is None:
            return False
        session.delete(note)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise


def get_all_tags() -> list[tuple[str, int]]:
    session = SessionFactory()
    rows = session.execute(
        select(Tag.name, func.count(NoteTag.note_id).label("cnt"))
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(NoteTag.note_id).desc())
    ).all()
    return [(row.name, row.cnt) for row in rows]


def get_notes_by_tag(tag: str) -> list[dict[str, Any]]:
    session = SessionFactory()
    rows = session.scalars(
        select(Note)
        .join(Note.tags)
        .where(Tag.name == tag)
        .order_by(Note.modified_at.desc())
    ).all()
    return [_note_to_dict(n) for n in rows]


def get_recent_notes(n: int = 10) -> list[dict[str, Any]]:
    session = SessionFactory()
    rows = session.scalars(
        select(Note).order_by(Note.modified_at.desc()).limit(n)
    ).all()
    return [_note_to_dict(n) for n in rows]


def full_sync(vault_path: str | Path) -> dict[str, int]:
    vault = Path(vault_path)
    disk_files = {p.name: p for p in vault.glob("**/*.md")}

    session = SessionFactory()
    db_filenames: set[str] = set(
        session.scalars(select(Note.filename)).all()
    )

    inserted = updated = deleted = 0

    for filename, path in disk_files.items():
        try:
            note_dict = parse_note(path)
            exists = filename in db_filenames
            upsert_note(note_dict)
            if exists:
                updated += 1
            else:
                inserted += 1
        except Exception as exc:
            print(f"  ⚠ Sync-Fehler bei {filename}: {exc}")

    # Remove DB entries whose files have been deleted
    for filename in db_filenames - set(disk_files.keys()):
        delete_note_from_db(filename)
        deleted += 1

    return {"inserted": inserted, "updated": updated, "deleted": deleted}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _note_to_dict(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "filename": note.filename,
        "title": note.title,
        "content": note.content,
        "word_count": note.word_count,
        "created_at": note.created_at,
        "modified_at": note.modified_at,
        "indexed_at": note.indexed_at,
        "tags": [t.name for t in note.tags],
        "links": [lnk.target_name for lnk in note.links],
    }
