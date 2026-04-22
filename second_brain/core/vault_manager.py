from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.markdown_parser import parse_note


class VaultManager:
    def __init__(self, vault_path: str | Path) -> None:
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all_notes(self) -> list[dict[str, Any]]:
        notes = []
        for md_file in sorted(self.vault_path.glob("**/*.md")):
            try:
                notes.append(parse_note(md_file))
            except Exception:
                pass
        return notes

    def get_note(self, filename: str) -> dict[str, Any] | None:
        path = self.vault_path / filename
        if not path.exists():
            # Try without extension
            path = self.vault_path / f"{filename}.md"
        if not path.exists():
            return None
        return parse_note(path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_note(
        self, title: str, content: str, tags: list[str] | None = None
    ) -> dict[str, Any]:
        tags = tags or []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        tag_yaml = "[" + ", ".join(tags) + "]" if tags else "[]"
        filename = _title_to_filename(title)
        path = self.vault_path / filename

        frontmatter = (
            f"---\n"
            f"title: {title}\n"
            f"created: {timestamp}\n"
            f"tags: {tag_yaml}\n"
            f"---\n\n"
        )
        path.write_text(frontmatter + content, encoding="utf-8")
        return parse_note(path)

    def update_note(self, filename: str, content: str) -> dict[str, Any]:
        path = self.vault_path / filename
        if not path.exists():
            raise FileNotFoundError(f"Notiz nicht gefunden: {filename}")

        existing = parse_note(path)
        fm = existing["frontmatter"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        tags = fm.get("tags", [])
        if isinstance(tags, list):
            tag_yaml = "[" + ", ".join(str(t) for t in tags) + "]"
        else:
            tag_yaml = str(tags)

        title = fm.get("title", path.stem)
        created = fm.get("created", timestamp)

        new_text = (
            f"---\n"
            f"title: {title}\n"
            f"created: {created}\n"
            f"modified: {timestamp}\n"
            f"tags: {tag_yaml}\n"
            f"---\n\n"
            + content
        )
        path.write_text(new_text, encoding="utf-8")
        return parse_note(path)

    def delete_note(self, filename: str) -> bool:
        path = self.vault_path / filename
        if not path.exists():
            return False
        path.unlink()
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_notes_fulltext(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for note in self.get_all_notes():
            if query_lower in note["raw_text"].lower():
                results.append(note)
        return results

    def get_backlinks(self, note_name: str) -> list[dict[str, Any]]:
        stem = Path(note_name).stem
        backlinks = []
        for note in self.get_all_notes():
            if stem in note["wikilinks"] and note["filename"] != note_name:
                backlinks.append(note)
        return backlinks

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        notes = self.get_all_notes()
        all_tags: set[str] = set()
        total_words = 0
        total_links = 0
        for note in notes:
            all_tags.update(note["tags"])
            total_words += note["word_count"]
            total_links += len(note["wikilinks"])
        return {
            "total_notes": len(notes),
            "total_words": total_words,
            "total_tags": len(all_tags),
            "total_links": total_links,
        }


def _title_to_filename(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    safe = safe.strip().replace(" ", "_")
    if not safe.endswith(".md"):
        safe += ".md"
    return safe
