"""Ports: abstract interfaces the application layer depends on.

The `application` layer (use cases) only talks to these `Protocol`s, never
to concrete infrastructure classes directly. This is the "dependency
inversion" piece of clean architecture: infrastructure implementations
(HTTP client, Postgres repository, SMTP notifier) depend *inward* on these
contracts, not the other way around. It also means unit tests can supply
trivial fakes instead of spinning up a real database or network call.
"""

from __future__ import annotations

from typing import Protocol

from meteoalarm_pipeline.domain.models import Alert, Country


class FeedFetcher(Protocol):
    """Fetches the raw feed payload for a given country."""

    async def fetch(self, country: Country) -> bytes:
        """Retrieve the raw ATOM/CAP feed body for ``country``.

        Args:
            country: The country whose feed should be fetched.

        Returns:
            The raw response body, as bytes (XML content).

        Raises:
            Exception: Implementations should raise on network/HTTP errors;
                callers are responsible for deciding whether to retry.
        """
        ...


class AlertParser(Protocol):
    """Parses a raw feed payload into validated domain :class:`Alert` objects."""

    def parse(self, raw_feed: bytes, country: Country) -> list[Alert]:
        """Parse ``raw_feed`` into a list of :class:`Alert` instances.

        Args:
            raw_feed: Raw XML bytes as returned by a :class:`FeedFetcher`.
            country: The country the feed belongs to (used to tag alerts).

        Returns:
            A list of validated alerts. Entries that fail validation are
            skipped and logged, not raised, so one bad entry doesn't sink
            the whole feed.
        """
        ...


class AlertRepository(Protocol):
    """Persists and queries alerts. Implemented by the storage backend."""

    async def upsert_many(self, alerts: list[Alert]) -> int:
        """Insert new alerts or update existing ones (matched by identifier).

        Returns:
            The number of rows affected.
        """
        ...


class Notifier(Protocol):
    """Sends a summary of alerts to interested recipients."""

    def send_summary(self, alerts: list[Alert]) -> None:
        """Send a formatted summary of ``alerts``.

        Args:
            alerts: The alerts to include in the summary.
        """
        ...
