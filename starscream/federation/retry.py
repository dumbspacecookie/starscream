"""Async retry helper for rate-limited federation APIs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE = (
    httpx.HTTPStatusError,
    httpx.TransportError,
    httpx.TimeoutException,
    ConnectionError,
    OSError,
)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
) -> T:
    """Run an async callable with exponential backoff on transient failures."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except _RETRYABLE as exc:
            last = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status not in _RETRYABLE_STATUS:
                raise
            if attempt + 1 >= attempts:
                raise
            delay = min(base_delay_s * (2**attempt), max_delay_s)
            logger.warning(
                "Federation retry in %.1fs (attempt %d/%d): %s",
                delay,
                attempt + 1,
                attempts,
                exc,
            )
            await asyncio.sleep(delay)
    if last:
        raise last
    raise RuntimeError("with_retry exhausted without result")
