"""Retry logic with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from pyscribe_core.errors import NetworkError, RetryExhaustedError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def with_retry(
    *,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (NetworkError,),
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exc: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        break

                    delay = backoff_factor * (2**attempt)
                    if jitter:
                        delay *= random.uniform(0.5, 1.5)  # nosec B311

                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.2fs",
                        attempt + 1,
                        max_retries + 1,
                        func.__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

            raise RetryExhaustedError(
                f"All {max_retries + 1} attempts failed for {func.__name__}",
                last_exception=last_exc,
            )

        return wrapper

    return decorator
