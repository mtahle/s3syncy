"""Token-bucket bandwidth limiter.

Usage with boto3 transfer callbacks::

    limiter = BandwidthLimiter(bytes_per_second=1_000_000)
    # In a boto3 Callback:
    limiter.consume(bytes_transferred)
"""

from __future__ import annotations

import threading
import time


class BandwidthLimiter:
    """Thread-safe token-bucket rate limiter (bytes/sec)."""

    def __init__(self, bytes_per_second: int = 0) -> None:
        """*bytes_per_second* == 0 means unlimited."""
        self._limit = bytes_per_second
        self._tokens = float(bytes_per_second) if bytes_per_second else 0.0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    @property
    def is_limited(self) -> bool:
        return self._limit > 0

    def consume(self, nbytes: int) -> None:
        """Block until *nbytes* worth of tokens are available."""
        if not self.is_limited:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            # Refill tokens based on elapsed time.
            self._tokens = min(
                float(self._limit),
                self._tokens + elapsed * self._limit,
            )
            self._tokens -= nbytes

        # If we over-consumed, sleep outside the lock.
        if self._tokens < 0:
            sleep_time = -self._tokens / self._limit
            time.sleep(sleep_time)
            with self._lock:
                self._tokens = 0.0
