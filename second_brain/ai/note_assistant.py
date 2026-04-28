"""Intelligent note assistant: tag suggestions, link suggestions, structuring."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ai.ollama_client import OllamaClient, OllamaConnectionError

_TAG_SYSTEM = (
    "Du bist ein Wissensmanagement-Assistent. "
    "Antworte IMMER ausschließlich mit valider JSON, kein erklärender Text."
)

_STRUCTURE_SYSTEM = (
    "Du bist ein Experte für Wissensmanagement und Markdown-Dokumentation. "
    "Gib NUR Markdown zurück, keinerlei Kommentare davor oder danach."
)

_EXPAND_SYSTEM = (
    "Du bist ein kreativer Wissensassistent. "
    "Antworte auf Deutsch und strukturiere deine Antwort klar."
)

_ACTION_SYSTEM = (
    "Du bist ein präziser Aufgaben-Extraktor. "
    "Antworte IMMER ausschließlich mit valider JSON, kein erklärender Text."
)

_INLINE_TAG_RE = re.compile(r"(?<!\w)#([\w/-]+)")
_ACTION_RE = re.compile(
    r"(?m)^(?:[-*]\s*\[[ x]\]\s+|TODO[:\s]+|FIXME[:\s]+|☐\s*|ACTION[:\s]+|Aufgabe[:\s]+)(.+)$",
    re.IGNORECASE,
)


def _parse_json_list(text: str) -> list:
    """Extract a JSON list from potentially messy LLM output."""
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return []


class NoteAssistant:
    def __init__(
        self,
        ollama: OllamaClient | None = None,
        rag: Any | None = None,
    ) -> None:
        self._ollama = ollama or OllamaClient()
        if rag is None:
            from ai.rag_engine import RAGEngine
            rag = RAGEngine(ollama=self._ollama)
        self._rag = rag

    # ------------------------------------------------------------------
    # Tag suggestion
    # ------------------------------------------------------------------

    def suggest_tags(
        self,
        note_content: str,
        existing_tags: list[str] | None = None,
    ) -> list[str]:
        existing_tags = existing_tags or []
        existing_str = ", ".join(existing_tags) if existing_tags else "keine"
        messages = [
            {
                "role": "user",
                "content": (
                    f"Analysiere diese Notiz und schlage 3-7 passende Tags vor.\n"
                    f"Bestehende Tags im Vault: {existing_str}.\n"
                    f"Antworte NUR mit einer JSON-Liste: [\"tag1\", \"tag2\"]\n\n"
                    f"Notiz:\n{note_content[:2000]}"
                ),
            }
        ]
        try:
            response = self._ollama.chat(messages, system_prompt=_TAG_SYSTEM)
            tags = _parse_json_list(response)
            return [str(t).lower().strip() for t in tags if t][:7]
        except OllamaConnectionError:
            return self._fallback_tags(note_content)

    def _fallback_tags(self, content: str) -> list[str]:
        inline = _INLINE_TAG_RE.findall(content)
        if inline:
            return list(dict.fromkeys(inline))[:7]
        words = re.findall(r"\b[A-Za-zÄÖÜäöüß]{5,}\b", content)
        freq: dict[str, int] = {}
        for w in words:
            freq[w.lower()] = freq.get(w.lower(), 0) + 1
        return sorted(freq, key=lambda k: -freq[k])[:5]

    # ------------------------------------------------------------------
    # Link suggestion
    # ------------------------------------------------------------------

    def suggest_links(
        self,
        note_content: str,
        all_notes_titles: list[str],
    ) -> list[dict[str, Any]]:
        try:
            candidates = self._rag.search_semantic(note_content[:1000], n_results=8)
        except OllamaConnectionError:
            return self._fallback_links(all_notes_titles)

        if not candidates:
            return self._fallback_links(all_notes_titles)

        try:
            candidates_text = "\n".join(
                f"- {c['title']} (Datei: {c['filename']})" for c in candidates
            )
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Notizinhalt:\n{note_content[:800]}\n\n"
                        f"Mögliche Links:\n{candidates_text}\n\n"
                        f"Welche dieser Notizen sollten verlinkt werden? "
                        f'Antworte mit JSON: [{{"filename":"...","title":"...","reason":"...","confidence":0.8}}]'
                    ),
                }
            ]
            response = self._ollama.chat(
                messages,
                system_prompt="Du bist ein Wissensmanagement-Assistent. Antworte nur mit JSON.",
            )
            validated = _parse_json_list(response)
            if validated and isinstance(validated[0], dict) and "filename" in validated[0]:
                return validated[:5]
        except (OllamaConnectionError, Exception):
            pass

        return [
            {
                "filename": c["filename"],
                "title": c["title"],
                "reason": "Semantisch ähnlicher Inhalt",
                "confidence": c["score"],
            }
            for c in candidates[:5]
        ]

    def _fallback_links(self, all_notes_titles: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "filename": f"{t.replace(' ', '_')}.md",
                "title": t,
                "reason": "Mögliche thematische Überschneidung",
                "confidence": 0.3,
            }
            for t in all_notes_titles[:3]
        ]

    # ------------------------------------------------------------------
    # Note structuring
    # ------------------------------------------------------------------

    def structure_note(self, raw_text: str) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    f"Strukturiere diesen Text als gut formatierte Markdown-Notiz "
                    f"mit passendem Titel, Abschnitten und einer kurzen Summary. "
                    f"Gib NUR Markdown zurück.\n\n{raw_text[:3000]}"
                ),
            }
        ]
        try:
            return self._ollama.chat(messages, system_prompt=_STRUCTURE_SYSTEM)
        except OllamaConnectionError:
            return self._fallback_structure(raw_text)

    def _fallback_structure(self, raw_text: str) -> str:
        first_line = raw_text.strip().splitlines()[0] if raw_text.strip() else "Notiz"
        title = first_line[:80].strip("# ").strip()
        return f"# {title}\n\n{raw_text.strip()}"

    # ------------------------------------------------------------------
    # Note expansion
    # ------------------------------------------------------------------

    def expand_note(self, note_dict: dict[str, Any]) -> str:
        title = note_dict.get("title", "")
        content = note_dict.get("content", "")[:2000]
        tags = ", ".join(note_dict.get("tags", []))
        messages = [
            {
                "role": "user",
                "content": (
                    f"Notiz: **{title}**\nTags: {tags}\n\n{content}\n\n"
                    f"Schlage vor:\n"
                    f"1. Wichtige Ergänzungen / fehlende Aspekte\n"
                    f"2. Offene Fragen die weiter untersucht werden sollten\n"
                    f"3. Verwandte Konzepte die verlinkt werden könnten"
                ),
            }
        ]
        try:
            return self._ollama.chat(messages, system_prompt=_EXPAND_SYSTEM)
        except OllamaConnectionError:
            return self._fallback_expand(note_dict)

    def _fallback_expand(self, note_dict: dict[str, Any]) -> str:
        title = note_dict.get("title", "diese Notiz")
        return (
            f"## Ergänzungsvorschläge für '{title}'\n\n"
            f"**Ergänzungen:** Füge Quellen, Beispiele oder konkrete Anwendungsfälle hinzu.\n\n"
            f"**Offene Fragen:** Welche Aspekte sind noch ungeklärt?\n\n"
            f"**Verwandte Konzepte:** Suche nach thematisch verwandten Notizen zum Verlinken."
        )

    # ------------------------------------------------------------------
    # Action item extraction
    # ------------------------------------------------------------------

    def extract_action_items(self, note_content: str) -> list[str]:
        messages = [
            {
                "role": "user",
                "content": (
                    f"Extrahiere alle TODOs, Aufgaben und Entscheidungspunkte aus dieser Notiz.\n"
                    f"Antworte NUR mit JSON: [\"Aufgabe 1\", \"Aufgabe 2\"]\n\n"
                    f"{note_content[:3000]}"
                ),
            }
        ]
        try:
            response = self._ollama.chat(messages, system_prompt=_ACTION_SYSTEM)
            items = _parse_json_list(response)
            return [str(i).strip() for i in items if i]
        except OllamaConnectionError:
            return self._fallback_actions(note_content)

    def _fallback_actions(self, content: str) -> list[str]:
        matches = _ACTION_RE.findall(content)
        # Also catch unchecked checkboxes
        checkbox_re = re.compile(r"[-*]\s*\[ \]\s*(.+)")
        checkboxes = checkbox_re.findall(content)
        all_items = [m.strip() for m in matches + checkboxes]
        seen: set[str] = set()
        result: list[str] = []
        for item in all_items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
