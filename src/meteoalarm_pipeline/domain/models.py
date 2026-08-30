"""Core domain models.

This module has no knowledge of HTTP, XML, or databases: it only describes
what an "Alert" *is*. Every other layer converts to/from these models at
its boundary, which is what lets us swap the feed format, the storage
engine, or the notification channel without touching business logic.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency


class Country(BaseModel):
    """A country tracked by the pipeline, with its MeteoAlarm feed URL and alert filters."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="ISO-like short code used internally, e.g. 'spain'.")
    name: str = Field(..., description="Human-readable country name, e.g. 'Spain'.")
    feed_url: str = Field(..., description="Full URL of the country's ATOM/CAP feed.")
    severities: list[str] = Field(
        default_factory=lambda: ["green", "yellow", "orange", "red"],
        description="Severity levels to track (green/yellow/orange/red); empty = all.",
    )
    certainties: list[str] = Field(
        default_factory=lambda: ["observed", "likely", "possible", "unlikely"],
        description="Certainty levels to track; empty = all.",
    )
    urgencies: list[str] = Field(
        default_factory=lambda: ["immediate", "expected", "future", "past"],
        description="Urgency levels to track; empty = all.",
    )


class Alert(BaseModel):
    """A single weather warning for one area, validated and normalised.

    Instances of this model are what the `application` layer works with.
    Field names intentionally mirror the CAP element names (minus the
    `cap:` prefix) so the mapping from XML stays obvious.
    """

    model_config = ConfigDict(frozen=True)

    identifier: str = Field(
        ..., description="Globally unique CAP identifier; used for dedup/upsert."
    )
    country_code: str = Field(..., description="Internal country code this alert belongs to.")
    area_desc: str = Field(..., description="Human-readable area name, e.g. 'Bizkaia interior'.")
    event: str = Field(
        ..., description="Free-text event name, e.g. 'Moderate thunderstorm warning'."
    )

    severity: Severity = Field(..., description="Alert severity (Moderate/Severe/Extreme).")
    certainty: Certainty = Field(..., description="Forecaster's confidence the event will occur.")
    urgency: Urgency = Field(..., description="How soon responsive action is recommended.")
    message_type: MessageType = Field(
        ..., description="Alert lifecycle state (Alert/Update/Cancel)."
    )

    sent_at: datetime = Field(
        ..., description="When the alert was sent by the national weather service."
    )
    effective_at: datetime = Field(..., description="When the alert becomes effective.")
    onset_at: datetime = Field(..., description="When the described weather is expected to start.")
    expires_at: datetime = Field(..., description="When the alert expires.")

    raw_title: str = Field(..., description="Original feed <title>, kept for display/debugging.")
    cap_detail_url: str = Field(
        ..., description="Link to the full CAP XML document for this alert."
    )

    @property
    def is_severe_or_worse(self) -> bool:
        """Convenience flag for filtering (e.g. summary emails, dashboards)."""
        return self.severity in (Severity.ORANGE, Severity.RED)
