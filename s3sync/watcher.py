"""Filesystem watcher — real-time events via watchdog + periodic full scan."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Dict

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from .config import SyncConfig
from .engine import SyncEngine

log = logging.getLogger(__name__)

# Debounce window (seconds): collapse rapid-fire events on the same path.
_DEBOUNCE_SEC = 0.5


class _DebouncedHandler(FileSystemEventHandler):
    """Debounces filesystem events before forwarding to the engine."""

    def __init__(self, engine: SyncEngine, sync_root: Path) -> None:
        super().__init__()
        self._engine = engine
        self._sync_root = sync_root
        self._pending: Dict[str, tuple] = {}  # path → (event_type, timestamp)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    # ── watchdog callbacks ──────────────────────────────────────────────

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path, "created")

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path, "modified")

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path, "deleted")

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path, "deleted")
            self._enqueue(event.dest_path, "created")

    # ── debounce logic ─────────────────────────────────────────────────

    def _enqueue(self, path: str, event_type: str) -> None:
        with self._lock:
            self._pending[path] = (event_type, time.monotonic())
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Timer(_DEBOUNCE_SEC, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            now = time.monotonic()
            ready = {
                p: ev
                for p, (ev, ts) in self._pending.items()
                if now - ts >= _DEBOUNCE_SEC
            }
            for p in ready:
                del self._pending[p]
            # If items remain, schedule another flush.
            if self._pending:
                self._timer = threading.Timer(_DEBOUNCE_SEC, self._flush)
                self._timer.daemon = True
                self._timer.start()
            else:
                self._timer = None

        for path_str, event_type in ready.items():
            try:
                self._engine.handle_event(
                    Path(path_str), event_type, self._sync_root,
                )
            except Exception as exc:
                log.error("Event handling error for %s: %s", path_str, exc)


class SyncWatcher:
    """Manages watchdog observers for all sync_dirs + periodic scans."""

    def __init__(self, cfg: SyncConfig, engine: SyncEngine) -> None:
        self._cfg = cfg
        self._engine = engine
        self._observer = Observer()
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start watching all configured directories."""
        for sync_dir in self._cfg.sync_dirs:
            handler = _DebouncedHandler(self._engine, sync_dir)
            self._observer.schedule(handler, str(sync_dir), recursive=True)
            log.info("Watching %s", sync_dir)
        self._observer.start()

    def run_periodic_scan(self) -> None:
        """Block and periodically trigger full scans until stopped."""
        while not self._stop_event.is_set():
            log.info("Starting periodic full scan …")
            try:
                self._engine.full_scan()
            except Exception as exc:
                log.error("Full scan error: %s", exc)
            self._stop_event.wait(self._cfg.scan_interval)

    def stop(self) -> None:
        self._stop_event.set()
        self._observer.stop()
        self._observer.join(timeout=5)
