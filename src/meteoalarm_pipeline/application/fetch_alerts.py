"""Use case: fetch and parse alerts for a set of countries.

This is the orchestration layer: it knows the *steps* (fetch, then parse,
per country, bounded in concurrency) but not *how* fetching or parsing
actually happens - that's delegated to the `FeedFetcher` and `AlertParser`
ports, so this function stays trivial to unit-test with fakes.
"""

from __future__ import annotations

import asyncio
import logging

from meteoalarm_pipeline.application.interfaces import AlertParser, FeedFetcher
from meteoalarm_pipeline.domain.models import Alert, Country

logger = logging.getLogger(__name__)


class FetchAlertsUseCase:
    """Fetches and parses alerts for multiple countries concurrently.

    Args:
        fetcher: Retrieves the raw feed bytes for a country.
        parser: Converts raw feed bytes into validated :class:`Alert` objects.
        max_concurrency: Maximum number of feeds fetched at the same time.
            Keeps us a well-behaved client rather than hammering the feed
            server with one request per country all at once.
    """

    def __init__(
        self,
        fetcher: FeedFetcher,
        parser: AlertParser,
        max_concurrency: int = 5,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(self, countries: list[Country]) -> list[Alert]:
        """Fetch and parse alerts for every country in ``countries``.

        A failure for one country (network error, parse error) is logged
        and that country simply contributes zero alerts - it does not
        abort the whole run.

        Args:
            countries: The countries to fetch alerts for.

        Returns:
            The combined list of alerts across all countries that
            succeeded.
        """
        logger.info("starting fetch for %d countries", len(countries))
        results = await asyncio.gather(
            *(self._fetch_one(country) for country in countries),
            return_exceptions=True,
        )

        all_alerts: list[Alert] = []
        for country, result in zip(countries, results, strict=True):
            if isinstance(result, BaseException):
                logger.error("country=%s failed entirely: %s", country.code, result)
                continue
            all_alerts.extend(result)

        logger.info(
            "fetch complete: %d total alerts across %d countries",
            len(all_alerts),
            len(countries),
        )
        return all_alerts

    async def _fetch_one(self, country: Country) -> list[Alert]:
        """Fetch and parse the feed for a single country, bounded by the semaphore."""
        async with self._semaphore:
            raw_feed = await self._fetcher.fetch(country)
        alerts = self._parser.parse(raw_feed, country)
        return self._filter_alerts(alerts, country)

    @staticmethod
    def _filter_alerts(alerts: list[Alert], country: Country) -> list[Alert]:
        """Filter alerts based on country's severity, certainty, and urgency criteria.

        If any filter is empty, all values are accepted for that dimension.
        Filters use lowercase enum names (e.g., "orange", "red" for Severity).
        """
        filtered = []
        for alert in alerts:
            # Check severity filter (empty = all severities accepted)
            if country.severities and alert.severity.name.lower() not in country.severities:
                continue
            # Check certainty filter (empty = all certainties accepted)
            if country.certainties and alert.certainty.name.lower() not in country.certainties:
                continue
            # Check urgency filter (empty = all urgencies accepted)
            if country.urgencies and alert.urgency.name.lower() not in country.urgencies:
                continue
            filtered.append(alert)

        skipped = len(alerts) - len(filtered)
        if skipped > 0:
            logger.debug(
                "country=%s filtered out %d alerts based on severity/certainty/urgency",
                country.code,
                skipped,
            )
        return filtered
