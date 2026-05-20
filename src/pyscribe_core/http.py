"""Async HTTP client with connection pooling, rate limiting, and structured error handling."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Any

import httpx

from pyscribe_core import __version__
from pyscribe_core.config import HttpConfig
from pyscribe_core.errors import NetworkError

logger = logging.getLogger(__name__)


class _RateLimiter:
    """Simple per-host rate limiter using a token bucket approach."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = asyncio.get_event_loop().time()
                # Drop timestamps outside the window
                cutoff = now - self.window
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                # Wait until the oldest timestamp expires
                wait = self._timestamps[0] - cutoff + 0.1
            logger.debug("Rate limiter: waiting %.2fs", wait)
            await asyncio.sleep(max(wait, 0.1))


class HttpClient:
    """Async HTTP client with connection pooling, retries, and GitHub auth."""

    def __init__(self, config: HttpConfig | None = None) -> None:
        self._config = config or HttpConfig()
        self._client: httpx.AsyncClient | None = None
        self._github_token = os.environ.get("PYSCRIBE_GITHUB_TOKEN")
        self._rate_limiter = _RateLimiter(max_requests=30, window_seconds=60)

    async def __aenter__(self) -> HttpClient:
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(self._config.timeout_seconds),
            follow_redirects=True,
            headers={
                "User-Agent": f"PyScribe/{__version__}",
            },
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise NetworkError("HTTP client not initialized. Use async context manager.")
        return self._client

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        client = self._require_client()
        effective_headers = (headers or {}).copy()

        # Rate limit all outbound requests
        await self._rate_limiter.acquire()

        # Inject GitHub token for API calls
        if "api.github.com" in url and self._github_token:
            effective_headers["Authorization"] = f"token {self._github_token}"
            effective_headers["Accept"] = "application/vnd.github.v3+json"

        try:
            response = await client.get(url, headers=effective_headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            self._maybe_handle_rate_limit(e)
            raise NetworkError(
                f"HTTP {e.response.status_code} for {url}: {e.response.text[:200]}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Request failed for {url}: {e}") from e

    async def get_bytes(self, url: str) -> bytes:
        client = self._require_client()
        await self._rate_limiter.acquire()

        if "api.github.com" in url and self._github_token:
            headers = {
                "Authorization": f"token {self._github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
        else:
            headers = {}

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            self._maybe_handle_rate_limit(e)
            raise NetworkError(
                f"HTTP {e.response.status_code} for {url}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Request failed for {url}: {e}") from e

    def _maybe_handle_rate_limit(self, exc: httpx.HTTPStatusError) -> None:
        """Introspect a failed response for rate-limit headers and log accordingly."""
        if exc.response.status_code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            limit_remaining = exc.response.headers.get("X-RateLimit-Remaining")
            logger.error(
                "Rate limited (429). Retry-After=%s, Remaining=%s",
                retry_after,
                limit_remaining,
            )
        elif exc.response.status_code == 403:
            scope = exc.response.headers.get("X-RateLimit-Limit")
            remaining = exc.response.headers.get("X-RateLimit-Remaining")
            if remaining == "0":
                logger.error(
                    "GitHub API quota exhausted. Limit=%s. Set PYSCRIBE_GITHUB_TOKEN to authenticate.",
                    scope,
                )
