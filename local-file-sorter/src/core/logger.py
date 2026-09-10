from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.mover import MoveResult


class OperationLogger:
    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = log_dir / f"sorter_{timestamp}.jsonl"
        self._file = self._path.open("a", encoding="utf-8")

    # ------------------------------------------------------------------
    def _write(self, entry: dict[str, Any]) -> None:
        entry["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        self._file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self._file.flush()

    # ------------------------------------------------------------------
    def log_move(self, result: MoveResult, dry_run: bool = False) -> None:
        if dry_run:
            status = "dry_run"
        else:
            status = "success" if result.success else "error"
        self._write(
            {
                "op_type": "move_file",
                "source": str(result.source_original),
                "destination": str(result.destination_final),
                "status": status,
                "error": result.error,
                "is_duplicate": result.is_duplicate,
            }
        )

    def log_folder(self, path: Path, success: bool,
                   error: str | None = None, dry_run: bool = False) -> None:
        if dry_run:
            status = "dry_run"
        else:
            status = "success" if success else "error"
        self._write(
            {
                "op_type": "create_folder",
                "source": None,
                "destination": str(path),
                "status": status,
                "error": error,
            }
        )

    def log_error(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._write(
            {
                "op_type": "error",
                "source": None,
                "destination": None,
                "status": "error",
                "error": message,
                "context": context or {},
            }
        )

    def get_session_path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._file.close()
