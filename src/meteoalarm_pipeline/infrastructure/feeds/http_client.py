"""Async HTTP fetcher for MeteoAlarm feed URLs, with retry/backoff.

Kept intentionally small: a single responsibility (get bytes from a URL,
resiliently), so it's trivially testable and swappable.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from meteoalarm_pipeline.domain.models import Country

logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    """Raised when a feed could not be fetched after all retry attempts."""


class HttpFeedFetcher:
    """Fetches feed bodies over HTTP(S) using a shared, reusable client.

    Args:
        client: A configured `httpx.AsyncClient`. Passed in (rather than
            created internally) so tests can inject a mocked transport
            and callers can share one connection pool across countries.
        max_attempts: Number of attempts per feed before giving up.
        backoff_seconds: Base delay between retries; doubles each attempt.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._client = client
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds

    async def fetch(self, country: Country) -> bytes:
        """Fetch the raw feed body for ``country``, retrying on failure.

        Args:
            country: The country whose feed URL should be fetched.

        Returns:
            The raw response body as bytes.

        Raises:
            FeedFetchError: If all retry attempts are exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                logger.debug(
                    "country=%s attempt=%d/%d fetching %s",
                    country.code,
                    attempt,
                    self._max_attempts,
                    country.feed_url,
                )
                response = await self._client.get(country.feed_url)
                response.raise_for_status()
                logger.info(
                    "country=%s fetch succeeded status=%d bytes=%d",
                    country.code,
                    response.status_code,
                    len(response.content),
                )
                return response.content
            except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
                last_error = exc
                logger.warning(
                    "country=%s attempt=%d/%d failed: %s",
                    country.code,
                    attempt,
                    self._max_attempts,
                    exc,
                )
                if attempt < self._max_attempts:
                    delay = self._backoff_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        raise FeedFetchError(
            f"Failed to fetch feed for {country.name} after {self._max_attempts} attempts"
        ) from last_error
