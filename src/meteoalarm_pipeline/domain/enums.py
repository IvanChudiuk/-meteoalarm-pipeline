"""Enumerations shared by the domain layer.

These enums encode vocabulary defined by the CAP (Common Alerting Protocol)
standard that MeteoAlarm feeds are built on. Keeping them here (rather than
as bare strings) gives us validation for free and makes invalid data fail
fast, at the parsing boundary, instead of silently propagating downstream.
"""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    """Alert severity, mirrors MeteoAlarm's traffic-light colour coding.

    MeteoAlarm titles alerts as "<Colour> <Event> Warning issued for ...".
    We map that colour directly to CAP's `cap:severity` element, which is
    the authoritative field, and keep the colour as a display concern only.
    """

    GREEN = "Minor"
    YELLOW = "Moderate"
    ORANGE = "Severe"
    RED = "Extreme"

    @classmethod
    def from_cap_value(cls, value: str) -> Severity:
        """Map a raw ``cap:severity`` string to a :class:`Severity` member.

        Args:
            value: Raw text from the ``<cap:severity>`` element (e.g. "Moderate").

        Returns:
            The matching :class:`Severity` member.

        Raises:
            ValueError: If ``value`` does not match any known severity.

        """
        normalized = value.strip().capitalize()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown CAP severity value: {value!r}")

    @property
    def display_colour(self) -> str:
        """Human-friendly colour name used in MeteoAlarm titles and emails."""
        return {
            Severity.GREEN: "Green",
            Severity.YELLOW: "Yellow",
            Severity.ORANGE: "Orange",
            Severity.RED: "Red",
        }[self]


class Certainty(StrEnum):
    """How certain the forecaster is that the event will occur."""

    OBSERVED = "Observed"
    LIKELY = "Likely"
    POSSIBLE = "Possible"
    UNLIKELY = "Unlikely"
    UNKNOWN = "Unknown"


class Urgency(StrEnum):
    """How quickly action is recommended, per the CAP spec."""

    IMMEDIATE = "Immediate"
    EXPECTED = "Expected"
    FUTURE = "Future"
    PAST = "Past"
    UNKNOWN = "Unknown"


class MessageType(StrEnum):
    """Lifecycle state of a CAP message."""

    ALERT = "Alert"
    UPDATE = "Update"
    CANCEL = "Cancel"
