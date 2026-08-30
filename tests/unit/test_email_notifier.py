from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from meteoalarm_pipeline.domain.enums import Certainty, MessageType, Severity, Urgency
from meteoalarm_pipeline.domain.models import Alert
from meteoalarm_pipeline.infrastructure.email.summary_notifier import SummaryEmailNotifier


def _make_alert(country_code: str = "spain", area: str = "Bizkaia interior") -> Alert:
    now = datetime(2026, 8, 30, 11, 25, tzinfo=ZoneInfo("Europe/Warsaw"))
    return Alert(
        identifier=f"{country_code}-{area}",
        country_code=country_code,
        area_desc=area,
        event="Moderate thunderstorm warning",
        severity=Severity.ORANGE,
        certainty=Certainty.LIKELY,
        urgency=Urgency.IMMEDIATE,
        message_type=MessageType.ALERT,
        sent_at=now,
        effective_at=now,
        onset_at=now,
        expires_at=now.replace(hour=18, minute=0),
        raw_title="Orange thunderstorm warning",
        cap_detail_url="https://example.invalid/detail",
    )


def test_render_summary_email_uses_local_europe_warsaw_time_and_expected_columns() -> None:
    notifier = SummaryEmailNotifier(
        from_addr="meteoalarm@example.test",
        to_addrs=["ops@example.test"],
        smtp_host="localhost",
        smtp_port=1025,
        timezone_name="Europe/Warsaw",
    )

    html = notifier.render_summary_email(
        [_make_alert()],
        execution_time=datetime(2026, 8, 30, 12, 0, tzinfo=ZoneInfo("Europe/Warsaw")),
    )

    assert "alert_color" in html
    assert "alert_type" in html
    assert "country_name" in html
    assert "zone_name" in html
    assert "alert_start" in html
    assert "alert_expires" in html
    assert "Generated at:" in html
    assert "CEST" in html
    assert "2026-08-30 12:00:00 CEST" in html


@patch("smtplib.SMTP")
def test_send_summary_sends_html_table_with_local_timezone(mock_smtp) -> None:
    notifier = SummaryEmailNotifier(
        from_addr="meteoalarm@example.test",
        to_addrs=["ops@example.test"],
        smtp_host="localhost",
        smtp_port=1025,
        timezone_name="Europe/Warsaw",
    )

    notifier.send_summary([_make_alert()])

    mock_smtp.return_value.send_message.assert_called_once()
    sent_message = mock_smtp.return_value.send_message.call_args.args[0]
    raw = sent_message.as_string()

    assert "alert_color" in raw
    assert "country_name" in raw
    assert "Generated at:" in raw
    assert "CEST" in raw
    assert "Spain" in raw
    assert "Bizkaia interior" in raw
