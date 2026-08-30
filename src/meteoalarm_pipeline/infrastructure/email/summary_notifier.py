"""SMTP summary notifier for MeteoAlarm alerts."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from meteoalarm_pipeline.domain.models import Alert

logger = logging.getLogger(__name__)


class SummaryEmailNotifier:
    """Send a summary email with a UTC conversion-safe HTML table."""

    def __init__(
        self,
        *,
        from_addr: str,
        to_addrs: list[str],
        smtp_host: str,
        smtp_port: int,
        timezone_name: str = "CET",
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.timezone_name = timezone_name
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.enabled = enabled

    def render_summary_email(
        self, alerts: list[Alert], execution_time: datetime | None = None
    ) -> str:
        """Render the summary email using a Jinja2 HTML template.

        The output includes the exact columns requested by the requirement:
        Execution_date, alert_color, alert_type, country_name, zone_name,
        alert_start, alert_expires.
        """
        tz = self._application_timezone()
        if execution_time is None:
            execution_time = datetime.now(tz=tz)

        rows = []
        for alert in alerts:
            rows.append(
                {
                    "alert_color": alert.severity.display_colour,
                    "alert_type": alert.event,
                    "country_name": self._country_name(alert.country_code),
                    "zone_name": alert.area_desc,
                    "alert_start": alert.onset_at.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "alert_expires": alert.expires_at.astimezone(tz).strftime(
                        "%Y-%m-%d %H:%M:%S %Z"
                    ),
                }
            )

        template_dir = Path(__file__).resolve().parent
        template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"), default_for_string=False
            ),
        )
        template = template_env.get_template("summary_email.html.jinja2")
        return template.render(
            execution_date=execution_time.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z"),
            rows=rows,
            alert_count=len(rows),
        )

    def _application_timezone(self) -> ZoneInfo:
        """Return the configured application timezone as a ZoneInfo object."""
        return ZoneInfo(self.timezone_name)

    @staticmethod
    def _country_name(country_code: str) -> str:
        """Map a country code to a human-readable display name."""
        names = {
            "spain": "Spain",
            "france": "France",
            "portugal": "Portugal",
            "italy": "Italy",
            "germany": "Germany",
        }
        return names.get(country_code.lower(), country_code.title())

    def send_summary(self, alerts: list[Alert]) -> None:
        """Send the email summary if enabled."""
        if not self.enabled:
            logger.info("SMTP summary email disabled; skipping send")
            return

        execution_time = datetime.now(tz=ZoneInfo("Europe/Warsaw"))
        html_body = self.render_summary_email(alerts, execution_time=execution_time)

        msg = EmailMessage()
        msg["Subject"] = "MeteoAlarm summary"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.set_content("Your email client does not support HTML messages.")
        msg.add_alternative(html_body, subtype="html")

        try:
            smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)
            try:
                if self.smtp_username and self.smtp_password:
                    smtp.starttls()
                    smtp.login(self.smtp_username, self.smtp_password)
                smtp.send_message(msg)
            finally:
                smtp.quit()
            logger.info("summary email sent to %s", ", ".join(self.to_addrs))
        except ConnectionRefusedError:
            logger.warning(
                "SMTP server not running on %s:%d; skipping email send. "
                "Start MailHog with: docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog",
                self.smtp_host,
                self.smtp_port,
            )
        except Exception:
            logger.exception("failed to send summary email via SMTP")
