"""Unit tests for the sync engine's stop/delete behaviour (background feature)."""

from copy import deepcopy

import pytest

from s3syncy.config import DEFAULTS, SyncConfig
from s3syncy.engine import SyncEngine
from s3syncy.index import SyncIndex
from s3syncy.patterns import ExclusionFilter

pytestmark = pytest.mark.unit


def _engine(tmp_path) -> tuple[SyncIndex, SyncEngine]:
    raw = deepcopy(DEFAULTS)
    raw["sync_dirs"] = [str(tmp_path)]
    raw["s3"]["bucket"] = "test-bucket"
    cfg = SyncConfig(raw, config_dir=tmp_path)
    index = SyncIndex(tmp_path / "test.db")
    exclusion = ExclusionFilter(tmp_path / "nope.ignore")
    engine = SyncEngine(cfg, index, exclusion)
    return index, engine


class TestStopSignal:
    def test_submit_returns_none_after_stop(self, tmp_path):
        index, engine = _engine(tmp_path)
        try:
            engine.request_stop()
            assert engine._submit(lambda: None) is None
        finally:
            engine.shutdown()
            index.close()

    def test_full_scan_returns_immediately_when_stopped(self, tmp_path):
        index, engine = _engine(tmp_path)
        try:
            (tmp_path / "a.txt").write_text("hello")
            engine.request_stop()
            engine.full_scan()
        finally:
            engine.shutdown()
            index.close()

    def test_upload_one_bails_when_stopped(self, tmp_path):
        index, engine = _engine(tmp_path)
        try:
            target = tmp_path / "a.txt"
            target.write_text("hello")
            engine.request_stop()
            engine._upload_one(target, "a.txt", tmp_path)
        finally:
            engine.shutdown()
            index.close()


class TestDeleteGuard:
    def test_delete_skips_when_upload_in_flight(self, tmp_path):
        index, engine = _engine(tmp_path)
        try:
            calls: list = []

            class _FakeS3:
                def delete_object(self, **kwargs):
                    calls.append(kwargs)
                    raise AssertionError("delete_object must not be called")

            engine._s3 = _FakeS3()
            with engine._lock:
                engine._active_keys.add("in-flight.txt")

            engine._delete_remote("in-flight.txt", tmp_path)

            assert calls == []
            assert index.get("in-flight.txt") is None
        finally:
            engine.shutdown()
            index.close()

    def test_delete_runs_when_not_in_flight(self, tmp_path):
        index, engine = _engine(tmp_path)
        try:
            calls: list = []

            class _FakeS3:
                def delete_object(self, **kwargs):
                    calls.append(kwargs)

            engine._s3 = _FakeS3()
            engine._delete_remote("plain.txt", tmp_path)

            assert calls == [{"Bucket": "test-bucket", "Key": "plain.txt"}]
        finally:
            engine.shutdown()
            index.close()
