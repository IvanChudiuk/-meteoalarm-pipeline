"""Parser for MeteoAlarm's ATOM feeds with embedded CAP extension elements.

MeteoAlarm publishes one ATOM feed per country. Each ``<entry>`` describes a
single weather warning for a single area, using standard ATOM elements
(``id``, ``title``, ``updated``) plus CAP-namespaced elements
(``cap:severity``, ``cap:onset``, etc.) for the meteorological detail.

Reference feed used during development:
https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain
"""

from __future__ import annotations

import logging
from datetime import datetime

from lxml import etree

from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency
from meteoalarm_pipeline.domain.models import Alert, Country

logger = logging.getLogger(__name__)

_ATOM_NS = "http://www.w3.org/2005/Atom"
_CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
_NAMESPACES = {"atom": _ATOM_NS, "cap": _CAP_NS}


class CapAtomParseError(Exception):
    """Raised when the feed's top-level structure cannot be parsed at all.

    Individual malformed *entries* are skipped and logged rather than
    raising this - it is reserved for cases where the whole document is
    not valid XML or is missing the root ``<feed>`` element.
    """


class CapAtomFeedParser:
    """Parses MeteoAlarm ATOM+CAP feeds into validated :class:`Alert` objects."""

    def parse(self, raw_feed: bytes, country: Country) -> list[Alert]:
        """Parse a raw ATOM+CAP feed into a list of alerts.

        Args:
            raw_feed: Raw XML bytes, as downloaded from the feed URL.
            country: The country this feed belongs to.

        Returns:
            Validated alerts. Entries that are malformed or fail domain
            validation are skipped (and logged as warnings), so a single
            bad entry never fails the whole batch.

        Raises:
            CapAtomParseError: If the document itself is not valid XML or
                has no ``<feed>`` root element.

        """
        try:
            root = etree.fromstring(raw_feed)
        except etree.XMLSyntaxError as exc:
            raise CapAtomParseError(f"Invalid XML for {country.name}: {exc}") from exc

        entries = root.findall("atom:entry", _NAMESPACES)
        logger.debug("country=%s found %d raw <entry> elements", country.code, len(entries))

        alerts: list[Alert] = []
        skipped = 0
        for entry in entries:
            alert = self._parse_entry(entry, country)
            if alert is None:
                skipped += 1
                continue
            alerts.append(alert)

        logger.info(
            "country=%s parsed=%d skipped=%d total_entries=%d",
            country.code,
            len(alerts),
            skipped,
            len(entries),
        )
        return alerts

    def _parse_entry(self, entry: etree._Element, country: Country) -> Alert | None:
        """Parse a single ``<entry>`` element, returning ``None`` on failure."""
        try:
            identifier = self._text(entry, "cap:identifier")
            area_desc = self._text(entry, "cap:areaDesc")
            event = self._text(entry, "cap:event")
            raw_title = self._text(entry, "atom:title")

            severity = Severity.from_cap_value(self._text(entry, "cap:severity"))
            certainty = Certainty(self._text(entry, "cap:certainty"))
            urgency = Urgency(self._text(entry, "cap:urgency"))
            message_type = MessageType(self._text(entry, "cap:message_type"))

            sent_at = self._parse_datetime(self._text(entry, "cap:sent"))
            # Fall back to cap:expires if cap:effective is not present
            try:
                effective_at = self._parse_datetime(self._text(entry, "cap:effective"))
            except AttributeError:
                effective_at = self._parse_datetime(self._text(entry, "cap:expires"))
            onset_at = self._parse_datetime(self._text(entry, "cap:onset"))
            expires_at = self._parse_datetime(self._text(entry, "cap:expires"))

            cap_detail_url = self._cap_detail_link(entry)

            return Alert(
                identifier=identifier,
                country_code=country.code,
                area_desc=area_desc,
                event=event,
                severity=severity,
                certainty=certainty,
                urgency=urgency,
                message_type=message_type,
                sent_at=sent_at,
                effective_at=effective_at,
                onset_at=onset_at,
                expires_at=expires_at,
                raw_title=raw_title,
                cap_detail_url=cap_detail_url,
            )
        except (ValueError, AttributeError) as exc:
            # AttributeError -> a required element was missing (`.text` on None).
            # ValueError -> an enum/datetime conversion failed.
            logger.warning("country=%s skipping malformed entry: %s", country.code, exc)
            return None

    @staticmethod
    def _text(entry: etree._Element, xpath: str) -> str:
        """Return the stripped text content of the first element matching ``xpath``.

        Raises:
            AttributeError: If no matching element is found (mirrors the
                error you'd get calling ``.text`` on ``None``), so callers
                can catch it alongside genuine value-conversion errors.

        """
        node = entry.find(xpath, _NAMESPACES)
        if node is None or node.text is None:
            raise AttributeError(f"missing required element: {xpath}")
        return node.text.strip()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Parse a CAP timestamp (ISO 8601 with explicit offset) into ``datetime``."""
        return datetime.fromisoformat(value)

    @staticmethod
    def _cap_detail_link(entry: etree._Element) -> str:
        """Extract the ``href`` of the ``application/cap+xml`` detail link."""
        for link in entry.findall("atom:link", _NAMESPACES):
            if link.get("type") == "application/cap+xml":
                href = link.get("href")
                if href:
                    return href
        raise AttributeError("missing cap+xml detail link")
