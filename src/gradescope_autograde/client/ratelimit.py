"""Rate limiter for Gradescope API requests."""

import time


class RateLimiter:
    """Enforces a minimum delay between consecutive requests."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last_request: float = 0.0

    def wait(self) -> None:
        """Block until enough time has elapsed since the last request."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()
