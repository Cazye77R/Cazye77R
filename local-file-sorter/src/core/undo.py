from __future__ import annotations

import json
from pathlib import Path

from src.core.mover import MoveResult, move_file


def undo_session(log_path: Path) -> list[MoveResult]:
    if not log_path.exists():
        raise FileNotFoundError(f"Log nicht gefunden: {log_path}")

    successful_moves: list[dict] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("op_type") == "move_file" and entry.get("status") == "success":
                successful_moves.append(entry)

    results: list[MoveResult] = []
    empty_dirs: list[Path] = []

    for entry in reversed(successful_moves):
        original_source = Path(entry["source"])
        current_location = Path(entry["destination"])

        if not current_location.exists():
            results.append(
                MoveResult(
                    success=False,
                    source_original=current_location,
                    destination_final=original_source,
                    error=f"Datei nicht mehr vorhanden: {current_location}",
                )
            )
            continue

        if original_source.exists():
            results.append(
                MoveResult(
                    success=False,
                    source_original=current_location,
                    destination_final=original_source,
                    error=f"Konflikt: Ziel existiert bereits: {original_source}",
                )
            )
            continue

        result = move_file(current_location, original_source)
        results.append(result)

        if result.success:
            parent = current_location.parent
            if parent.exists() and not any(parent.iterdir()):
                empty_dirs.append(parent)

    if empty_dirs:
        print("\nHinweis: Folgende (nun leere) Ordner wurden NICHT gelöscht:")
        for d in empty_dirs:
            print(f"  {d}")

    return results
