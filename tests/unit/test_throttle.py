"""Unit tests for throttle module."""

import time
import pytest

from s3syncy.throttle import BandwidthLimiter


class TestBandwidthLimiter:
    """Test bandwidth throttling logic."""

    def test_unlimited_bandwidth(self):
        """Test that 0 limit means unlimited (no throttling)."""
        limiter = BandwidthLimiter(0)

        start = time.monotonic()
        limiter.consume(1_000_000)  # 1MB
        elapsed = time.monotonic() - start

        # Should complete instantly (no throttling)
        assert elapsed < 0.1

    def test_bandwidth_throttling(self, monkeypatch):
        """Test that bandwidth is throttled correctly (after initial burst)."""
        # 100 KB/s limit
        limiter = BandwidthLimiter(100_000)

        # Drain the initial token bucket (BandwidthLimiter starts full).
        limiter.consume(100_000)

        sleeps: list[float] = []
        monkeypatch.setattr(throttle.time, "sleep", lambda s: sleeps.append(s))

        limiter.consume(50_000)  # should require ~0.5s of sleep at 100KB/s
        assert len(sleeps) == 1
        assert sleeps[0] == pytest.approx(0.5, rel=0.25)
    def test_multiple_consumes(self):
        """Test multiple consume calls."""
        limiter = BandwidthLimiter(100_000)  # 100 KB/s

        start = time.monotonic()
        limiter.consume(25_000)  # 25 KB
        limiter.consume(25_000)  # 25 KB
        elapsed = time.monotonic() - start

        # Total 50KB at 100KB/s = ~0.5 seconds
        assert 0.4 < elapsed < 0.7

    def test_small_chunks_no_excessive_waiting(self):
        """Test that very small chunks don't cause excessive waiting."""
        limiter = BandwidthLimiter(1_000_000)  # 1 MB/s

        start = time.monotonic()
        for _ in range(10):
            limiter.consume(1000)  # 1KB each
        elapsed = time.monotonic() - start

        # 10KB at 1MB/s should be very fast
        assert elapsed < 0.1
