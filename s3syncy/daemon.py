"""Main daemon — ties config, engine, watcher together and handles signals."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import SyncConfig, load_config
from .engine import SyncEngine
from .index import SyncIndex
from .patterns import ExclusionFilter
from .watcher import SyncWatcher

log = logging.getLogger("s3sync")


# ---------------------------------------------------------------------------
# setup helpers


def _setup_logging(cfg: SyncConfig) -> None:
    """Configure the root s3sync logger."""
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  [%(threadName)s]  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger("s3sync")
    root.setLevel(getattr(logging, cfg.log_level, logging.INFO))
    root.handlers.clear()

    # Console handler.
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Optional rotating file handler.
    if cfg.log_file:
        fh = logging.handlers.RotatingFileHandler(
            cfg.log_file,
            maxBytes=cfg.log_max_size,
            backupCount=cfg.log_backup_count,
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)



def _apply_resource_limits(cfg: SyncConfig) -> None:
    """Best-effort soft memory cap (unix only)."""
    if cfg.max_memory_mb <= 0:
        return
    if platform.system() in ("Linux", "Darwin"):
        try:
            import resource

            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            target = cfg.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (target, hard))
            log.info("Soft memory limit set to %d MB", cfg.max_memory_mb)
        except (ImportError, ValueError, OSError) as exc:
            log.debug("Could not set memory limit: %s", exc)


# ---------------------------------------------------------------------------
# daemon


class SyncDaemon:
    """Top-level orchestrator. Call ``run()`` to start blocking."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        pid_file: str | Path | None = None,
        state_file: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.pid_file = (
            Path(pid_file).resolve()
            if pid_file
            else self.config_path.with_suffix(self.config_path.suffix + ".pid")
        )
        self.state_file = (
            Path(state_file).resolve()
            if state_file
            else self.config_path.with_suffix(self.config_path.suffix + ".state.json")
        )

        self._shutdown_event = threading.Event()
        self._paused_event = threading.Event()
        self._runtime_lock = threading.RLock()
        self._reload_lock = threading.Lock()
        self._cfg_watch_thread: threading.Thread | None = None

        self.cfg = load_config(self.config_path)
        _setup_logging(self.cfg)
        _apply_resource_limits(self.cfg)

        self.index: SyncIndex
        self.exclusion: ExclusionFilter
        self.engine: SyncEngine
        self.watcher: SyncWatcher | None = None
        self._build_runtime(self.cfg)

        self._config_mtime: float = 0.0
        self._exclude_mtime: float = 0.0
        self._refresh_watch_mtimes()

    # -- lifecycle ---------------------------------------------------------

    def run(self) -> None:
        """Start the daemon (blocks until SIGINT / SIGTERM)."""
        self._install_signal_handlers()
        self._write_pid_file()
        self._write_state("running")

        with self._runtime_lock:
            self._start_watcher_locked()

        self._cfg_watch_thread = threading.Thread(
            target=self._watch_inputs_loop,
            daemon=True,
            name="cfg-watch",
        )
        self._cfg_watch_thread.start()

        log.info("s3sync daemon starting — watching %s", self.cfg.sync_dirs)

        try:
            while not self._shutdown_event.is_set():
                if self._paused_event.is_set():
                    self._shutdown_event.wait(0.5)
                    continue

                with self._runtime_lock:
                    engine = self.engine
                    scan_interval = self.cfg.scan_interval

                log.info("Starting periodic full scan …")
                try:
                    engine.full_scan()
                except Exception as exc:
                    log.error("Full scan error: %s", exc)

                self._wait_for_next_scan(scan_interval)
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received — initiating graceful shutdown")
            self._shutdown_event.set()
        finally:
            # Ensure shutdown event is always set so background threads can observe shutdown
            self._shutdown_event.set()
            self._graceful_shutdown()

    def stop(self) -> None:
        """Trigger a graceful shutdown from another thread."""
        self._shutdown_event.set()
        with self._runtime_lock:
            if self.watcher is not None:
                self.watcher.stop()
                self.watcher = None

    def pause(self) -> None:
        with self._runtime_lock:
            if self._paused_event.is_set():
                return
            self._paused_event.set()
            if self.watcher is not None:
                self.watcher.stop()
                self.watcher = None
            self._write_state("paused")
            log.info("Daemon paused")

    def resume(self) -> None:
        with self._runtime_lock:
            if not self._paused_event.is_set():
                return
            self._paused_event.clear()
            if not self._shutdown_event.is_set():
                self._start_watcher_locked()
            self._write_state("running")
            log.info("Daemon resumed")

    def reload(self, reason: str = "manual") -> None:
        """Reload config/exclusions and rebuild runtime components."""
        with self._reload_lock:
            try:
                new_cfg = load_config(self.config_path)
            except Exception as exc:
                log.error("Config reload failed: %s", exc)
                return

            with self._runtime_lock:
                old_cfg = self.cfg
                if self.watcher is not None:
                    self.watcher.stop()
                    self.watcher = None
                self.engine.shutdown()
                self.index.close()

                self.cfg = new_cfg
                _apply_resource_limits(self.cfg)
                self._build_runtime(self.cfg)
                self._refresh_watch_mtimes()

                if (
                    old_cfg.log_level != self.cfg.log_level
                    or old_cfg.log_file != self.cfg.log_file
                ):
                    log.warning(
                        "Logging config changed. Restart daemon to apply new logging sinks."
                    )

                if not self._paused_event.is_set() and not self._shutdown_event.is_set():
                    self._start_watcher_locked()

            self._write_state(
                "paused" if self._paused_event.is_set() else "running",
                extra={"last_reload_reason": reason},
            )
            log.info("Reload complete (%s)", reason)

    # -- internals ---------------------------------------------------------

    def _build_runtime(self, cfg: SyncConfig) -> None:
        db_path = (
            Path(cfg.log_file).parent / ".s3sync_index.db"
            if cfg.log_file
            else Path(".s3sync_index.db")
        )
        self.index = SyncIndex(db_path)
        self.exclusion = ExclusionFilter(cfg.exclude_file)
        self.engine = SyncEngine(cfg, self.index, self.exclusion)
        self.watcher = SyncWatcher(cfg, self.engine)

    def _start_watcher_locked(self) -> None:
        # Watchdog observer objects are single-use; always create a fresh watcher.
        self.watcher = SyncWatcher(self.cfg, self.engine)
        self.watcher.start()

    def _wait_for_next_scan(self, seconds: int) -> None:
        end = time.monotonic() + max(1, seconds)
        while time.monotonic() < end:
            if self._shutdown_event.is_set() or self._paused_event.is_set():
                return
            remaining = end - time.monotonic()
            self._shutdown_event.wait(min(0.5, max(0.0, remaining)))

    def _install_signal_handlers(self) -> None:
        def _stop_handler(signum, frame):
            log.info("Received signal %s — shutting down …", signum)
            self.stop()

        signal.signal(signal.SIGINT, _stop_handler)
        signal.signal(signal.SIGTERM, _stop_handler)

        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._reload_handler)
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, self._pause_handler)
        if hasattr(signal, "SIGUSR2"):
            signal.signal(signal.SIGUSR2, self._resume_handler)

    def _pause_handler(self, signum, frame) -> None:
        log.info("Pause signal received")
        self.pause()

    def _resume_handler(self, signum, frame) -> None:
        log.info("Resume signal received")
        self.resume()

    def _reload_handler(self, signum, frame) -> None:
        log.info("Reload signal received")
        self.reload(reason="SIGHUP")

    def _watch_inputs_loop(self) -> None:
        while not self._shutdown_event.is_set():
            if self._shutdown_event.wait(1.5):
                return
            if self._inputs_changed():
                log.info("Detected config/exclude file change, reloading")
                self.reload(reason="file_change")

    def _inputs_changed(self) -> bool:
        config_mtime = self._safe_mtime(self.config_path)
        exclude_path = self.cfg.exclude_file
        exclude_mtime = self._safe_mtime(exclude_path)
        return (
            config_mtime != self._config_mtime
            or exclude_mtime != self._exclude_mtime
        )

    def _refresh_watch_mtimes(self) -> None:
        self._config_mtime = self._safe_mtime(self.config_path)
        self._exclude_mtime = self._safe_mtime(self.cfg.exclude_file)

    @staticmethod
    def _safe_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    # -- pid/state ---------------------------------------------------------

    def _write_pid_file(self) -> None:
        existing_pid = self._read_pid_file()
        if existing_pid and self._is_process_alive(existing_pid):
            raise RuntimeError(f"Daemon already running (pid {existing_pid})")

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "config_path": str(self.config_path),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.pid_file.write_text(json.dumps(payload), encoding="utf-8")

    def _read_pid_file(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            if raw.startswith("{"):
                payload = json.loads(raw)
                return int(payload.get("pid", 0)) or None
            return int(raw)
        except Exception:
            return None

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _remove_pid_file(self) -> None:
        pid = self._read_pid_file()
        if pid != os.getpid():
            return
        try:
            self.pid_file.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Failed to remove PID file %s: %s", self.pid_file, exc)

    def _write_state(self, status: str, extra: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "status": status,
            "pid": os.getpid(),
            "config_path": str(self.config_path),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            payload.update(extra)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _graceful_shutdown(self) -> None:
        log.info("Shutting down …")
        with self._runtime_lock:
            if self.watcher is not None:
                self.watcher.stop()
                self.watcher = None
            self.engine.shutdown()
            self.index.close()
        self._write_state("stopped")
        self._remove_pid_file()
        log.info("Goodbye.")
