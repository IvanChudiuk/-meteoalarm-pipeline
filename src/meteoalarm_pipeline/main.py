"""Composition root and entrypoint.

This is the only module allowed to know about every concrete
implementation at once - it wires infrastructure classes into the use
case and runs it. Everything else in the codebase depends on interfaces,
not on this module.

Current slice: fetch -> parse -> validate -> print.
Database persistence and the summary email are added in later slices.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from meteoalarm_pipeline.application.fetch_alerts import FetchAlertsUseCase
from meteoalarm_pipeline.config import COUNTRIES, get_settings
from meteoalarm_pipeline.domain.enums import Severity
from meteoalarm_pipeline.domain.models import Alert
from meteoalarm_pipeline.infrastructure.feeds.cap_atom_parser import CapAtomFeedParser
from meteoalarm_pipeline.infrastructure.feeds.http_client import HttpFeedFetcher
from meteoalarm_pipeline.logging_config import configure_logging

logger = logging.getLogger(__name__)

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.RED: 0,
    Severity.ORANGE: 1,
    Severity.YELLOW: 2,
    Severity.GREEN: 3,
}


def _print_summary(alerts: list[Alert]) -> None:
    """Print a human-readable summary of fetched alerts, grouped by country.

    This stands in for the future "send_summary" email use case - same
    shape of output, different destination.
    """
    if not alerts:
        print("No active alerts found.")
        return

    alerts_by_country: dict[str, list[Alert]] = {}
    for alert in alerts:
        alerts_by_country.setdefault(alert.country_code, []).append(alert)

    print(f"\n{'=' * 60}")
    print(f"MeteoAlarm summary: {len(alerts)} alert(s) across {len(alerts_by_country)} countries")
    print(f"{'=' * 60}")

    for country_code, country_alerts in sorted(alerts_by_country.items()):
        sorted_alerts = sorted(country_alerts, key=lambda a: _SEVERITY_ORDER[a.severity])
        print(f"\n{country_code.upper()} ({len(sorted_alerts)} alerts)")
        for alert in sorted_alerts[:10]:  # cap printed lines per country for readability
            print(
                f"  [{alert.severity.display_colour:6s}] {alert.event:30s} - {alert.area_desc} "
                f"(expires {alert.expires_at:%Y-%m-%d %H:%M %Z})"
            )
        if len(sorted_alerts) > 10:
            print(f"  ... and {len(sorted_alerts) - 10} more")


async def run() -> list[Alert]:
    """Run the fetch -> parse -> validate slice for all configured countries.

    Returns:
        The combined list of alerts fetched, for callers (e.g. tests or a
        future scheduler) that want the data rather than just the printout.

    """
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("run starting for %d countries", len(COUNTRIES))

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        fetcher = HttpFeedFetcher(client=client)
        parser = CapAtomFeedParser()
        use_case = FetchAlertsUseCase(
            fetcher=fetcher,
            parser=parser,
            max_concurrency=settings.max_concurrency,
        )
        alerts = await use_case.execute(COUNTRIES)

    _print_summary(alerts)
    logger.info("run finished")
    return alerts


def main() -> None:
    """Synchronous entrypoint, e.g. for `python -m meteoalarm_pipeline.main`."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
