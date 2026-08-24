"""Unit tests for :class:`FetchAlertsUseCase`.

Both dependencies (fetcher, parser) are simple hand-written fakes that
satisfy the `application.interfaces` Protocols. This is the payoff of
depending on interfaces rather than concrete infrastructure: no network,
no XML, no event loop surprises - just the orchestration logic under test.
"""

from __future__ import annotations

import pytest

from meteoalarm_pipeline.application.fetch_alerts import FetchAlertsUseCase
from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency
from meteoalarm_pipeline.domain.models import Alert, Country

from datetime import datetime, timezone


def _make_alert(country_code: str, area: str) -> Alert:
    """Build a minimal, valid Alert for test purposes."""
    now = datetime.now(timezone.utc)
    return Alert(
        identifier=f"{country_code}-{area}",
        country_code=country_code,
        area_desc=area,
        event="Moderate rain warning",
        severity=Severity.YELLOW,
        certainty=Certainty.LIKELY,
        urgency=Urgency.FUTURE,
        message_type=MessageType.ALERT,
        sent_at=now,
        effective_at=now,
        onset_at=now,
        expires_at=now,
        raw_title="Yellow Rain Warning issued for Test",
        cap_detail_url="https://example.invalid/detail",
    )


class FakeFetcher:
    """Returns pre-set bytes per country code, or raises if configured to fail."""

    def __init__(self, failing_codes: set[str] | None = None) -> None:
        self._failing_codes = failing_codes or set()

    async def fetch(self, country: Country) -> bytes:
        if country.code in self._failing_codes:
            raise ConnectionError(f"simulated network failure for {country.code}")
        return f"<feed for {country.code}>".encode()


class FakeParser:
    """Returns one canned alert per country, regardless of feed content."""

    def parse(self, raw_feed: bytes, country: Country) -> list[Alert]:
        return [_make_alert(country.code, "Test Area")]


@pytest.mark.asyncio
async def test_execute_combines_alerts_from_all_countries() -> None:
    """Alerts from every country should be combined into a single list."""
    countries = [
        Country(code="spain", name="Spain", feed_url="https://example.invalid/es"),
        Country(code="france", name="France", feed_url="https://example.invalid/fr"),
    ]
    use_case = FetchAlertsUseCase(fetcher=FakeFetcher(), parser=FakeParser())

    alerts = await use_case.execute(countries)

    assert len(alerts) == 2
    assert {a.country_code for a in alerts} == {"spain", "france"}


@pytest.mark.asyncio
async def test_execute_continues_when_one_country_fails() -> None:
    """A fetch failure for one country should not prevent others from succeeding."""
    countries = [
        Country(code="spain", name="Spain", feed_url="https://example.invalid/es"),
        Country(code="france", name="France", feed_url="https://example.invalid/fr"),
    ]
    use_case = FetchAlertsUseCase(fetcher=FakeFetcher(failing_codes={"france"}), parser=FakeParser())

    alerts = await use_case.execute(countries)

    assert len(alerts) == 1
    assert alerts[0].country_code == "spain"


@pytest.mark.asyncio
async def test_execute_with_no_countries_returns_empty_list() -> None:
    """Calling execute with an empty country list should return an empty list, not error."""
    use_case = FetchAlertsUseCase(fetcher=FakeFetcher(), parser=FakeParser())

    alerts = await use_case.execute([])

    assert alerts == []
