"""Unit tests for :class:`CapAtomFeedParser`.

Uses a trimmed, real-world sample of the Spain feed (see
``tests/fixtures/spain_sample.atom.xml``) so the test exercises the actual
element structure MeteoAlarm publishes, including one deliberately
malformed entry to verify skip-and-continue behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency
from meteoalarm_pipeline.domain.models import Country
from meteoalarm_pipeline.infrastructure.feeds.cap_atom_parser import (
    CapAtomFeedParser,
    CapAtomParseError,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def spain() -> Country:
    """A sample country matching the fixture feed."""
    return Country(code="spain", name="Spain", feed_url="https://example.invalid/spain")


@pytest.fixture
def spain_feed_bytes() -> bytes:
    """Raw bytes of the trimmed Spain sample feed."""
    return (FIXTURES_DIR / "spain_sample.atom.xml").read_bytes()


class TestCapAtomFeedParser:
    """Tests for :meth:`CapAtomFeedParser.parse`."""

    def test_parses_valid_entries(self, spain_feed_bytes: bytes, spain: Country) -> None:
        """All well-formed entries in the fixture should be parsed successfully."""
        parser = CapAtomFeedParser()

        alerts = parser.parse(spain_feed_bytes, spain)

        # Fixture has 4 entries, one deliberately malformed -> 3 expected.
        assert len(alerts) == 3

    def test_skips_malformed_entry_without_raising(
        self, spain_feed_bytes: bytes, spain: Country
    ) -> None:
        """An entry missing a required CAP field should be skipped, not raise."""
        parser = CapAtomFeedParser()

        alerts = parser.parse(spain_feed_bytes, spain)

        identifiers = {alert.identifier for alert in alerts}
        assert "2.49.0.0.724.0.ES.999999999999.000000TEST000000000" not in identifiers

    def test_maps_fields_correctly_for_first_entry(
        self, spain_feed_bytes: bytes, spain: Country
    ) -> None:
        """Spot-check that every field on a known-good entry maps correctly."""
        parser = CapAtomFeedParser()

        alerts = parser.parse(spain_feed_bytes, spain)
        bizkaia_alert = next(a for a in alerts if a.area_desc == "Bizkaia interior")

        assert bizkaia_alert.country_code == "spain"
        assert bizkaia_alert.event == "Moderate thunderstorm warning"
        assert bizkaia_alert.severity == Severity.YELLOW
        assert bizkaia_alert.certainty == Certainty.LIKELY
        assert bizkaia_alert.urgency == Urgency.IMMEDIATE
        assert bizkaia_alert.message_type == MessageType.ALERT
        assert bizkaia_alert.identifier == "2.49.0.0.724.0.ES.260823153609.754802TOTO231899369"
        assert bizkaia_alert.cap_detail_url.startswith("https://feeds.meteoalarm.org/")
        assert bizkaia_alert.sent_at.isoformat() == "2026-08-23T15:36:09+00:00"

    def test_severity_reflects_orange_for_severe_entries(
        self, spain_feed_bytes: bytes, spain: Country
    ) -> None:
        """CAP 'Severe' should map to our ORANGE severity tier."""
        parser = CapAtomFeedParser()

        alerts = parser.parse(spain_feed_bytes, spain)
        lleida_alert = next(a for a in alerts if "Lleida" in a.area_desc)

        assert lleida_alert.severity == Severity.ORANGE
        assert lleida_alert.is_severe_or_worse is True

    def test_raises_on_invalid_xml(self, spain: Country) -> None:
        """Completely invalid XML should raise CapAtomParseError, not fail silently."""
        parser = CapAtomFeedParser()

        with pytest.raises(CapAtomParseError):
            parser.parse(b"<not><valid", spain)

    def test_empty_feed_returns_empty_list(self, spain: Country) -> None:
        """A syntactically valid feed with zero entries should return an empty list."""
        parser = CapAtomFeedParser()
        empty_feed = (
            b'<?xml version="1.0"?>'
            b'<feed xmlns="http://www.w3.org/2005/Atom" '
            b'xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2"></feed>'
        )

        alerts = parser.parse(empty_feed, spain)

        assert alerts == []
