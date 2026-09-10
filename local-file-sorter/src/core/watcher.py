"""Background folder watcher – polls a directory for newly appeared files.

Detection only. No file operation happens here — the caller decides what to
do once new files are reported (per the pipeline rules, a plan still needs
explicit user confirmation before anything is moved).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from src.core.scanner import scan_folder

DEFAULT_POLL_INTERVAL = 5.0


class FolderWatcher:
    def __init__(
        self,
        folder: Path,
        on_new_files: Callable[[list[Path]], None],
        recursive: bool = False,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._folder        = folder
        self._on_new_files   = on_new_files
        self._recursive      = recursive
        self._poll_interval  = poll_interval
        self._stop_event     = threading.Event()
        self._thread: threading.Thread | None = None
        self._known: set[Path] = set()

    def _snapshot(self) -> set[Path]:
        try:
            return {f.path for f in scan_folder(self._folder, self._recursive) if not f.is_dir}
        except (NotADirectoryError, OSError):
            return set()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._known = self._snapshot()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval):
            current = self._snapshot()
            new_files = sorted(current - self._known)
            self._known = current
            if new_files:
                try:
                    self._on_new_files(new_files)
                except Exception:
                    pass
