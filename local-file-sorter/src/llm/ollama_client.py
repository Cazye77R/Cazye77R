from __future__ import annotations

import json
from pathlib import Path

import ollama
from pydantic import ValidationError

from src.core.mover import is_safe_destination
from src.core.scanner import FileInfo
from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from src.llm.schemas import OpType, SortPlan


class PlanValidationError(Exception):
    pass


class OllamaClient:
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self._client = ollama.Client(host=base_url)

    # ------------------------------------------------------------------
    def generate_plan(
        self,
        files: list[FileInfo],
        user_command: str,
        target_folder: Path,
    ) -> SortPlan:
        user_prompt = build_user_prompt(files, user_command, target_folder)
        plan, error = self._call_and_parse(user_prompt, retry_hint=None)
        if plan is not None:
            self._validate_sources(plan, target_folder)
            return plan

        # Single retry with error context
        retry_hint = (
            f"Deine vorherige Antwort war ungültig: {error}. "
            "Antworte ausschließlich als JSON gemäß Schema. "
            "Keine Erklärungen, kein Text außerhalb des JSON-Objekts."
        )
        plan, error = self._call_and_parse(user_prompt, retry_hint=retry_hint)
        if plan is not None:
            self._validate_sources(plan, target_folder)
            return plan

        raise PlanValidationError(
            f"LLM-Antwort konnte nach Retry nicht geparst werden: {error}"
        )

    # ------------------------------------------------------------------
    def _call_and_parse(
        self,
        user_prompt: str,
        retry_hint: str | None,
    ) -> tuple[SortPlan | None, str]:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if retry_hint:
            messages.append({"role": "user", "content": retry_hint})

        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                format="json",
            )
        except Exception as exc:
            return None, f"Ollama-Verbindungsfehler: {exc}"

        raw = response.message.content or ""

        try:
            plan = SortPlan.model_validate_json(raw)
            return plan, ""
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return None, str(exc)

    # ------------------------------------------------------------------
    def _validate_sources(self, plan: SortPlan, target_folder: Path) -> None:
        problems: list[str] = []
        for action in plan.actions:
            if action.op_type != OpType.move:
                continue
            if action.source is None:
                problems.append(
                    f"move-Aktion ohne source: destination={action.destination}"
                )
                continue
            src = Path(action.source)
            if not src.exists():
                problems.append(f"source existiert nicht: {src}")
            if not is_safe_destination(src, target_folder):
                problems.append(
                    f"source liegt außerhalb des Zielordners: {src} "
                    f"(erlaubt: {target_folder})"
                )
        if problems:
            raise PlanValidationError(
                "Plan enthält ungültige move-Aktionen:\n" + "\n".join(f"  • {p}" for p in problems)
            )
