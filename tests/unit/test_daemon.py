"""Unit tests for the daemon lifecycle (background running feature)."""

import json
import os

import pytest

from s3syncy.daemon import SyncDaemon

pytestmark = pytest.mark.unit


def _write_config(tmp_path, scan_interval: int = 30) -> None:
    sync = tmp_path / "sync"
    sync.mkdir(exist_ok=True)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
sync_dirs: [{sync}]
s3:
  bucket: test-bucket
scan_interval_seconds: {scan_interval}
resources:
  max_memory_mb: 0
logging:
  level: ERROR
  file: {tmp_path / "log.txt"}
""",
        encoding="utf-8",
    )


def _make_daemon(tmp_path) -> SyncDaemon:
    _write_config(tmp_path)
    return SyncDaemon(
        tmp_path / "config.yaml",
        pid_file=tmp_path / "d.pid",
        state_file=tmp_path / "d.state.json",
    )


class TestDaemonLifecycle:
    def test_pid_file_roundtrip(self, tmp_path):
        daemon = _make_daemon(tmp_path)
        daemon._write_pid_file()
        assert daemon._read_pid_file() == os.getpid()
        daemon._remove_pid_file()
        assert not daemon.pid_file.exists()

    def test_stop_without_run_does_not_crash(self, tmp_path):
        """Finding #1: stop() must not crash when the watcher never started."""
        daemon = _make_daemon(tmp_path)
        daemon.stop()
        assert daemon._shutdown_event.is_set()

    def test_pause_resume_state_transitions(self, tmp_path):
        daemon = _make_daemon(tmp_path)

        daemon.pause()
        assert json.loads(daemon.state_file.read_text(encoding="utf-8"))["status"] == "paused"

        daemon.resume()
        assert json.loads(daemon.state_file.read_text(encoding="utf-8"))["status"] == "running"

        daemon.stop()
        assert daemon._shutdown_event.is_set()

    def test_reload_applies_config_change(self, tmp_path):
        daemon = _make_daemon(tmp_path)
        assert daemon.cfg.scan_interval == 30

        _write_config(tmp_path, scan_interval=60)
        daemon.reload(reason="test")

        assert daemon.cfg.scan_interval == 60
        daemon.stop()
