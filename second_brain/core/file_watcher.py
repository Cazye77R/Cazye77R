"""Live-sync Vault → SQLite via watchdog with per-file debounce."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from core.database import delete_note_from_db, upsert_note
from core.markdown_parser import parse_note

_DEBOUNCE_SECONDS = 1.0


def _try_embed(note_dict: dict) -> None:
    try:
        from ai.embedder import embed_note  # type: ignore[import]
        embed_note(note_dict)
    except ImportError:
        pass
    except Exception as exc:
        print(f"  ⚠ Embedding fehlgeschlagen ({note_dict.get('filename', '?')}): {exc}")


def _try_remove_embedding(filename: str) -> None:
    try:
        from ai.embedder import delete_embedding  # type: ignore[import]
        delete_embedding(filename)
    except ImportError:
        pass
    except Exception as exc:
        print(f"  ⚠ Embedding-Löschung fehlgeschlagen ({filename}): {exc}")


class _Handler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str, str], None] | None) -> None:
        super().__init__()
        self._callback = callback
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Debounce
    # ------------------------------------------------------------------

    def _schedule(self, path: str, action: Callable[[], None]) -> None:
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing:
                existing.cancel()
            t = threading.Timer(_DEBOUNCE_SECONDS, action)
            t.daemon = True
            self._timers[path] = t
            t.start()

    def _cancel(self, path: str) -> None:
        with self._lock:
            t = self._timers.pop(path, None)
            if t:
                t.cancel()

    # ------------------------------------------------------------------
    # Watchdog event handlers
    # ------------------------------------------------------------------

    def on_created(self, event: FileCreatedEvent) -> None:
        if not isinstance(event, FileCreatedEvent) or not event.src_path.endswith(".md"):
            return
        self._schedule(event.src_path, lambda: self._handle_upsert(event.src_path))

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not isinstance(event, FileModifiedEvent) or not event.src_path.endswith(".md"):
            return
        self._schedule(event.src_path, lambda: self._handle_upsert(event.src_path))

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not isinstance(event, FileDeletedEvent) or not event.src_path.endswith(".md"):
            return
        self._cancel(event.src_path)
        self._schedule(event.src_path, lambda: self._handle_delete(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if not isinstance(event, FileMovedEvent):
            return
        if event.src_path.endswith(".md"):
            self._cancel(event.src_path)
            self._schedule(event.src_path, lambda: self._handle_delete(event.src_path))
        if event.dest_path.endswith(".md"):
            self._schedule(event.dest_path, lambda: self._handle_upsert(event.dest_path))

    # ------------------------------------------------------------------
    # Actions (run after debounce)
    # ------------------------------------------------------------------

    def _handle_upsert(self, src_path: str) -> None:
        path = Path(src_path)
        if not path.exists():
            return
        try:
            note_dict = parse_note(path)
            upsert_note(note_dict)
            _try_embed(note_dict)
            if self._callback:
                self._callback("upsert", note_dict["filename"])
        except Exception as exc:
            print(f"  ⚠ Watcher-Fehler beim Verarbeiten von {path.name}: {exc}")

    def _handle_delete(self, src_path: str) -> None:
        filename = Path(src_path).name
        try:
            delete_note_from_db(filename)
            _try_remove_embedding(filename)
            if self._callback:
                self._callback("delete", filename)
        except Exception as exc:
            print(f"  ⚠ Watcher-Fehler beim Löschen von {filename}: {exc}")


class VaultWatcher:
    def __init__(self) -> None:
        self._observer: Observer | None = None

    def start_watching(
        self,
        vault_path: str | Path,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        if self._observer and self._observer.is_alive():
            return

        handler = _Handler(callback)
        self._observer = Observer()
        self._observer.schedule(handler, str(vault_path), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop_watching(self) -> None:
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
        self._observer = None

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
