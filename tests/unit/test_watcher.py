"""Unit tests for the filesystem watcher (daemon background feature)."""

import time
from copy import deepcopy

import pytest
from watchdog.events import FileCreatedEvent, FileModifiedEvent

from s3syncy.config import DEFAULTS, SyncConfig
from s3syncy.watcher import SyncWatcher, _DebouncedHandler

pytestmark = pytest.mark.unit


def _cfg(tmp_path) -> SyncConfig:
    raw = deepcopy(DEFAULTS)
    raw["sync_dirs"] = [str(tmp_path)]
    raw["resources"]["max_memory_mb"] = 0
    return SyncConfig(raw, config_dir=tmp_path)


class _FakeEngine:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def handle_event(self, path, event_type, sync_root) -> None:
        self.events.append((str(path), event_type))


class TestSyncWatcher:
    def test_stop_without_start_does_not_crash(self, tmp_path):
        """stop() must be safe when the observer was never started."""
        watcher = SyncWatcher(_cfg(tmp_path), _FakeEngine())
        watcher.stop()

    def test_stop_is_idempotent(self, tmp_path):
        watcher = SyncWatcher(_cfg(tmp_path), _FakeEngine())
        watcher.stop()
        watcher.stop()


class TestDebouncedHandler:
    def test_events_are_debounced_and_flushed(self, tmp_path):
        engine = _FakeEngine()
        handler = _DebouncedHandler(engine, tmp_path)

        target = str(tmp_path / "a.txt")
        handler.on_created(FileCreatedEvent(target))
        handler.on_modified(FileModifiedEvent(target))

        time.sleep(1.0)

        assert (target, "modified") in engine.events

    def test_moved_event_becomes_delete_and_create(self, tmp_path):
        from watchdog.events import FileMovedEvent

        engine = _FakeEngine()
        handler = _DebouncedHandler(engine, tmp_path)

        src = str(tmp_path / "src.txt")
        dest = str(tmp_path / "dest.txt")
        handler.on_moved(FileMovedEvent(src, dest))

        time.sleep(1.0)

        assert (src, "deleted") in engine.events
        assert (dest, "created") in engine.events
