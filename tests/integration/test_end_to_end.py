"""End-to-end test for the complete alert fetching pipeline.

Tests the full flow from raw feed bytes through parsing to validated alerts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from meteoalarm_pipeline.application.fetch_alerts import FetchAlertsUseCase
from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency
from meteoalarm_pipeline.domain.models import Alert, Country
from meteoalarm_pipeline.infrastructure.feeds.cap_atom_parser import CapAtomFeedParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def spain() -> Country:
    """A sample country matching the fixture feed."""
    return Country(code="spain", name="Spain", feed_url="https://example.invalid/spain")


@pytest.fixture
def spain_feed_bytes() -> bytes:
    """Raw bytes of the trimmed Spain sample feed."""
    return (FIXTURES_DIR / "spain_sample.atom.xml").read_bytes()


class TestEndToEnd:
    """End-to-end tests for the complete alert pipeline."""

    @pytest.mark.asyncio
    async def test_fetch_parse_full_pipeline(
        self, spain: Country, spain_feed_bytes: bytes
    ) -> None:
        """Test the complete flow: fetch -> parse -> return alerts.

        Verifies:
        - Feed fetcher returns the raw feed bytes
        - Parser converts feed bytes to alerts
        - Malformed entries are skipped
        - All valid alerts have expected properties
        """
        # Set up mock fetcher that returns the sample feed
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.return_value = spain_feed_bytes

        # Set up real parser
        parser = CapAtomFeedParser()

        # Create use case with mock fetcher and real parser
        use_case = FetchAlertsUseCase(
            fetcher=mock_fetcher,
            parser=parser,
            max_concurrency=1,
        )

        # Execute the use case
        alerts = await use_case.execute([spain])

        # Verify results
        # Fixture has 4 entries, 1 malformed -> 3 valid alerts expected
        assert len(alerts) == 3

        # Verify fetcher was called once for Spain
        mock_fetcher.fetch.assert_called_once_with(spain)

        # Verify alert properties are correctly parsed
        assert all(isinstance(alert, Alert) for alert in alerts)
        assert all(alert.country_code == "spain" for alert in alerts)

        # Verify different severity levels are present
        severities = {alert.severity for alert in alerts}
        assert Severity.YELLOW in severities
        assert Severity.ORANGE in severities

        # Verify first alert (Yellow Thunderstorm)
        yellow_alert = next(a for a in alerts if a.severity == Severity.YELLOW)
        assert yellow_alert.area_desc == "Bizkaia interior"
        assert yellow_alert.event == "Moderate thunderstorm warning"
        assert yellow_alert.certainty == Certainty.LIKELY
        assert yellow_alert.urgency == Urgency.IMMEDIATE
        assert yellow_alert.message_type == MessageType.ALERT
        assert "Bizkaia interior" in yellow_alert.raw_title

    @pytest.mark.asyncio
    async def test_multiple_countries_pipeline(
        self, spain: Country, spain_feed_bytes: bytes
    ) -> None:
        """Test fetching alerts for multiple countries (with one succeeding).

        Verifies:
        - Use case handles multiple countries
        - Each country is fetched and parsed independently
        - Failures in one country don't affect others
        """
        france = Country(code="france", name="France", feed_url="https://example.invalid/france")

        # Mock fetcher: Spain succeeds, France fails
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = [
            spain_feed_bytes,  # Spain succeeds
            Exception("Network error for France"),  # France fails
        ]

        parser = CapAtomFeedParser()
        use_case = FetchAlertsUseCase(fetcher=mock_fetcher, parser=parser, max_concurrency=2)

        # Execute - should not raise despite France failing
        alerts = await use_case.execute([spain, france])

        # Verify Spain's alerts were parsed but France contributed nothing
        assert len(alerts) == 3
        assert all(alert.country_code == "spain" for alert in alerts)

        # Verify fetcher was called for both countries
        assert mock_fetcher.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_alert_attributes_complete(
        self, spain: Country, spain_feed_bytes: bytes
    ) -> None:
        """Test that all alert attributes are properly populated from feed.

        Verifies timestamp parsing, URL extraction, and enum conversions.
        """
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.return_value = spain_feed_bytes

        parser = CapAtomFeedParser()
        use_case = FetchAlertsUseCase(fetcher=mock_fetcher, parser=parser, max_concurrency=1)

        alerts = await use_case.execute([spain])

        # Pick an orange alert to test all fields
        orange_alert = next(a for a in alerts if a.severity == Severity.ORANGE)

        # Verify identifier is present and from feed
        assert orange_alert.identifier.startswith("2.49.0.0.724.0.ES")

        # Verify timestamps are parsed
        assert orange_alert.sent_at is not None
        assert orange_alert.effective_at is not None
        assert orange_alert.onset_at is not None
        assert orange_alert.expires_at is not None

        # Verify detail URL is extracted
        assert orange_alert.cap_detail_url.startswith("https://feeds.meteoalarm.org/")

        # Verify all required fields are present
        assert orange_alert.area_desc
        assert orange_alert.event
        assert orange_alert.raw_title
