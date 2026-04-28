"""Daily briefing agent: summarises recent activity and surfaces insights."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ai.note_assistant import NoteAssistant
from ai.ollama_client import OllamaClient, OllamaConnectionError
from core.config import BASE_DIR

_BRIEFINGS_DIR = BASE_DIR / "data" / "briefings"

_INSIGHT_SYSTEM = (
    "Du bist ein kreativer Wissensassistent. "
    "Antworte in 2-3 prägnanten deutschen Sätzen."
)


class BriefingAgent:
    def __init__(
        self,
        ollama: OllamaClient | None = None,
        rag: Any | None = None,
        vault_manager: Any | None = None,
    ) -> None:
        self._ollama = ollama or OllamaClient()
        if rag is None:
            from ai.rag_engine import RAGEngine
            rag = RAGEngine(ollama=self._ollama)
        self._rag = rag
        if vault_manager is None:
            from core.vault_manager import VaultManager
            from core.config import VAULT_DIR
            vault_manager = VaultManager(VAULT_DIR)
        self._vault = vault_manager
        self._assistant = NoteAssistant(ollama=self._ollama, rag=self._rag)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate_daily_briefing(self) -> dict[str, Any]:
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")

        recent_notes = self._get_recent_notes()
        suggested_connections = self._find_missing_connections(recent_notes)
        open_todos = self._collect_todos(recent_notes)
        stats = self._vault.get_stats()
        insight = self._generate_insight(recent_notes)

        briefing = {
            "date": date_str,
            "summary": self._build_summary(recent_notes, stats),
            "recent_notes": [
                {"filename": n["filename"], "title": n["title"]}
                for n in recent_notes
            ],
            "suggested_connections": suggested_connections,
            "open_todos": open_todos,
            "stats": stats,
            "insight": insight,
        }

        self._save_briefing(briefing, date_str)
        return briefing

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_recent_notes(self, days: int = 7) -> list[dict[str, Any]]:
        from core.database import get_recent_notes
        cutoff = datetime.utcnow() - timedelta(days=days)
        all_recent = get_recent_notes(n=50)
        return [
            n for n in all_recent
            if isinstance(n.get("modified_at"), datetime)
            and n["modified_at"] >= cutoff
        ]

    def _find_missing_connections(
        self,
        recent_notes: list[dict[str, Any]],
        n: int = 5,
    ) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()

        for note in recent_notes[:10]:
            try:
                related = self._rag.find_related_notes(note, n=3)
            except Exception:
                continue

            existing_links = set(note.get("wikilinks", []))
            for rel in related:
                rel_stem = Path(rel["filename"]).stem
                note_stem = Path(note["filename"]).stem
                pair = tuple(sorted([note_stem, rel_stem]))

                if rel_stem not in existing_links and pair not in seen_pairs:
                    seen_pairs.add(pair)
                    suggestions.append(
                        {
                            "from": {
                                "filename": note["filename"],
                                "title": note.get("title", note["filename"]),
                            },
                            "to": {
                                "filename": rel["filename"],
                                "title": rel.get("title", rel["filename"]),
                            },
                            "score": rel.get("score", 0.0),
                            "reason": f"Ähnlichkeitsscore: {rel.get('score', 0):.2f}",
                        }
                    )

            if len(suggestions) >= n:
                break

        return suggestions[:n]

    def _collect_todos(
        self,
        recent_notes: list[dict[str, Any]],
    ) -> list[str]:
        todos: list[str] = []
        seen: set[str] = set()

        for note in recent_notes:
            content = note.get("content", "")
            if not content:
                # Fall back to DB content field
                content = note.get("content", "")
            try:
                items = self._assistant.extract_action_items(content)
            except Exception:
                items = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    todos.append(item)

        return todos[:20]

    def _generate_insight(self, recent_notes: list[dict[str, Any]]) -> str:
        if not recent_notes:
            return "Noch keine Notizen vorhanden. Starte noch heute!"

        note = random.choice(recent_notes[:5])
        content = note.get("content", "")[:1000]
        title = note.get("title", "")
        messages = [
            {
                "role": "user",
                "content": (
                    f"Notiz '{title}':\n{content}\n\n"
                    f"Welcher überraschende Gedanke, interessante Verbindung "
                    f"oder weiterführende Frage ergibt sich aus dieser Notiz?"
                ),
            }
        ]
        try:
            return self._ollama.chat(messages, system_prompt=_INSIGHT_SYSTEM)
        except OllamaConnectionError:
            return f"Interessant: '{title}' hat {note.get('word_count', 0)} Wörter und wartet auf weitere Vertiefung."

    def _build_summary(
        self,
        recent_notes: list[dict[str, Any]],
        stats: dict[str, int],
    ) -> str:
        n = len(recent_notes)
        total = stats.get("total_notes", 0)
        words = stats.get("total_words", 0)
        if n == 0:
            return f"Keine neuen Notizen in den letzten 7 Tagen. Vault: {total} Notizen, {words} Wörter."
        titles = ", ".join(f"'{r['title']}'" for r in recent_notes[:3])
        more = f" und {n - 3} weitere" if n > 3 else ""
        return (
            f"{n} Notiz(en) in den letzten 7 Tagen: {titles}{more}. "
            f"Vault gesamt: {total} Notizen, {words} Wörter."
        )

    def _save_briefing(self, briefing: dict[str, Any], date_str: str) -> None:
        _BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
        path = _BRIEFINGS_DIR / f"{date_str}.md"

        recent_lines = "\n".join(
            f"- [[{n['filename'].removesuffix('.md')}|{n['title']}]]"
            for n in briefing["recent_notes"]
        ) or "_Keine_"

        conn_lines = "\n".join(
            f"- [[{c['from']['filename'].removesuffix('.md')}]] ↔ [[{c['to']['filename'].removesuffix('.md')}]] — {c['reason']}"
            for c in briefing["suggested_connections"]
        ) or "_Keine Vorschläge_"

        todo_lines = "\n".join(f"- [ ] {t}" for t in briefing["open_todos"]) or "_Keine_"

        stats = briefing["stats"]
        md = (
            f"---\n"
            f"title: Briefing {date_str}\n"
            f"created: {date_str}\n"
            f"tags: [briefing, automatisch]\n"
            f"---\n\n"
            f"# Tages-Briefing {date_str}\n\n"
            f"## Zusammenfassung\n{briefing['summary']}\n\n"
            f"## Neueste Notizen (letzte 7 Tage)\n{recent_lines}\n\n"
            f"## Vorgeschlagene Verbindungen\n{conn_lines}\n\n"
            f"## Offene Aufgaben\n{todo_lines}\n\n"
            f"## Vault-Statistiken\n"
            f"- Notizen: {stats.get('total_notes', 0)}\n"
            f"- Wörter: {stats.get('total_words', 0)}\n"
            f"- Tags: {stats.get('total_tags', 0)}\n"
            f"- Links: {stats.get('total_links', 0)}\n\n"
            f"## Heutiger Gedanke\n{briefing['insight']}\n"
        )
        path.write_text(md, encoding="utf-8")
