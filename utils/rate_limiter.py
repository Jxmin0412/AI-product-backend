"""
Rate limiting utilities for LLM API calls and web scraping.

Provides:
- TokenBucketRateLimiter: For LLM API rate limiting
- ScrapingRateLimiter: Per-domain delay for web scraping
"""
import asyncio
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for async operations.
    Tokens refill at a steady rate; bursts are allowed up to bucket capacity.
    """

    def __init__(
        self,
        rate: int = 20,
        burst: int = 5,
        per_seconds: int = 60,
    ):
        self.rate = rate
        self.burst = burst
        self.per_seconds = per_seconds
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

        logger.info(
            f"TokenBucketRateLimiter: {rate} req/{per_seconds}s, burst={burst}"
        )

    async def acquire(self, tokens: int = 1) -> None:
        """Block until *tokens* are available, then consume them."""
        async with self._lock:
            while True:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # How long until we have enough?
                deficit = tokens - self.tokens
                wait = (deficit / self.rate) * self.per_seconds
                logger.debug(f"Rate-limited, waiting {wait:.2f}s")
                # Release the lock while sleeping so other coroutines can check
                # (we re-acquire at top of loop).
                self._lock.release()
                await asyncio.sleep(wait)
                await self._lock.acquire()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        if elapsed > 0:
            refill = (elapsed / self.per_seconds) * self.rate
            self.tokens = min(self.burst, self.tokens + refill)
            self.last_update = now


class ScrapingRateLimiter:
    """
    Per-domain rate limiter that enforces a minimum delay between
    consecutive requests to the same domain.
    """

    def __init__(self, default_delay: float = 2.0):
        self.default_delay = default_delay
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str, delay: Optional[float] = None) -> None:
        """Wait until enough time has passed since the last request to *domain*."""
        delay = delay if delay is not None else self.default_delay

        async with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0.0)
            elapsed = now - last

            if elapsed < delay:
                wait = delay - elapsed
                logger.debug(f"Scraping rate-limit for {domain}: waiting {wait:.2f}s")
                await asyncio.sleep(wait)

            self._last_request[domain] = time.monotonic()
