from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import ollama
from pydantic import ValidationError

from src.core.mover import is_safe_destination
from src.core.scanner import FileInfo
from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from src.llm.schemas import OpType, SortAction, SortPlan


class PlanValidationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Standalone validation – importable for tests
# ---------------------------------------------------------------------------

def validate_plan(plan: SortPlan, target_folder: Path) -> None:
    """Raise PlanValidationError if any action is unsafe or invalid.

    Checks (all must pass; one failure rejects the entire plan):
    - Every destination is inside target_folder
    - Every move source is inside target_folder
    - Every move source exists on disk
    - Every move has a non-None source
    """
    problems: list[str] = []
    for i, action in enumerate(plan.actions, start=1):
        prefix = f"Aktion {i} ({action.op_type.value})"

        # Destination must be inside target_folder
        if not is_safe_destination(action.destination, target_folder):
            problems.append(
                f"{prefix}: destination außerhalb des Zielordners: "
                f"{action.destination}  (erlaubt: {target_folder})"
            )

        if action.op_type == OpType.move:
            if action.source is None:
                problems.append(f"{prefix}: move-Aktion ohne source")
                continue
            # Source must be inside target_folder
            if not is_safe_destination(action.source, target_folder):
                problems.append(
                    f"{prefix}: source außerhalb des Zielordners: "
                    f"{action.source}"
                )
            # Source must exist
            if not action.source.exists():
                problems.append(
                    f"{prefix}: source existiert nicht: {action.source}"
                )

    if problems:
        raise PlanValidationError(
            "Plan abgelehnt – ungültige Aktion(en) gefunden:\n"
            + "\n".join(f"  • {p}" for p in problems)
        )


# ---------------------------------------------------------------------------

class OllamaClient:
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model    = model
        self._client  = ollama.Client(host=base_url)

    # ------------------------------------------------------------------
    def generate_plan(
        self,
        files: list[FileInfo],
        user_command: str,
        target_folder: Path,
        batch_size: int = 100,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> SortPlan:
        """Generate and validate a SortPlan, chunking large file lists."""
        if len(files) <= batch_size:
            plan = self._generate_single(files, user_command, target_folder)
            if progress_cb:
                progress_cb(1, 1)
            return plan

        # ---- chunked mode ----
        chunks = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
        total  = len(chunks)
        all_actions: list[SortAction] = []
        summaries:   list[str]        = []

        for idx, chunk in enumerate(chunks, start=1):
            if progress_cb:
                progress_cb(idx, total)
            chunk_plan = self._generate_single(chunk, user_command, target_folder)
            all_actions.extend(chunk_plan.actions)
            summaries.append(chunk_plan.summary)

        combined_summary = (
            f"Konsolidierter Plan ({total} Chunks): "
            + "; ".join(summaries[:2])
            + ("…" if total > 2 else "")
        )
        return SortPlan(actions=all_actions, summary=combined_summary)

    # ------------------------------------------------------------------
    def _generate_single(
        self,
        files: list[FileInfo],
        user_command: str,
        target_folder: Path,
    ) -> SortPlan:
        user_prompt = build_user_prompt(files, user_command, target_folder)
        plan, error = self._call_and_parse(user_prompt, retry_hint=None)
        if plan is not None:
            validate_plan(plan, target_folder)
            return plan

        retry_hint = (
            f"Deine vorherige Antwort war ungültig: {error}. "
            "Antworte ausschließlich als JSON gemäß Schema. "
            "Keine Erklärungen, kein Text außerhalb des JSON-Objekts."
        )
        plan, error = self._call_and_parse(user_prompt, retry_hint=retry_hint)
        if plan is not None:
            validate_plan(plan, target_folder)
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
            {"role": "user",   "content": user_prompt},
        ]
        if retry_hint:
            messages.append({"role": "user", "content": retry_hint})

        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                format="json",
            )
        except ollama.ResponseError:
            raise   # API errors (404 model not found, etc.) must not be swallowed
        except Exception as exc:
            return None, f"Ollama-Verbindungsfehler: {exc}"

        raw = response.message.content or ""

        try:
            plan = SortPlan.model_validate_json(raw)
            return plan, ""
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return None, str(exc)
