"""Unit tests for throttle module."""

import pytest
import s3syncy.throttle as throttle

pytestmark = pytest.mark.unit

class TestBandwidthLimiter:
    """Test bandwidth throttling logic."""

    def test_unlimited_bandwidth(self):
        """Test that 0 limit means unlimited (no throttling)."""
        limiter = throttle.BandwidthLimiter(0)

        start = time.monotonic()
        limiter.consume(1_000_000)  # 1MB
        elapsed = time.monotonic() - start

        # Should complete instantly (no throttling)
        assert elapsed < 0.1

    def test_bandwidth_throttling(self, monkeypatch):
        """Test that bandwidth is throttled correctly (after initial burst)."""
        # 100 KB/s limit
        limiter = throttle.BandwidthLimiter(100_000)

        # Drain the initial token bucket (BandwidthLimiter starts full).
        limiter.consume(100_000)

        sleeps: list[float] = []
        monkeypatch.setattr(throttle.time, "sleep", lambda s: sleeps.append(s))

        limiter.consume(50_000)  # should require ~0.5s of sleep at 100KB/s
        assert len(sleeps) == 1
        assert sleeps[0] == pytest.approx(0.5, rel=0.25)
    def test_multiple_consumes(self):
        """Test multiple consume calls."""
        limiter = throttle.BandwidthLimiter(100_000)  # 100 KB/s

        start = time.monotonic()
        limiter.consume(25_000)  # 25 KB
        limiter.consume(25_000)  # 25 KB
        elapsed = time.monotonic() - start

        # Total 50KB at 100KB/s = ~0.5 seconds
        assert 0.4 < elapsed < 0.7

    def test_small_chunks_no_excessive_waiting(self, monkeypatch):
        """Test that very small chunks don't cause excessive waiting."""
        limiter = throttle.BandwidthLimiter(1_000_000)  # 1 MB/s

        sleeps: list[float] = []
        monkeypatch.setattr(throttle.time, "sleep", lambda s: sleeps.append(s))

        for _ in range(10):
            limiter.consume(1000)  # 1KB each

        assert sleeps == []
