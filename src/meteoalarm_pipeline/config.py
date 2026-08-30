"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env``
file) via `pydantic-settings`. Nothing outside this module should read
`os.environ` directly - this keeps configuration centralised and typed.

Countries are loaded from a YAML file (config/countries.yaml) to allow
easy enable/disable and alert filtering by severity, certainty, and urgency.
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from meteoalarm_pipeline.domain.models import Country


def _load_countries_from_yaml() -> list[Country]:
    """Load countries from config/countries.yaml and return only enabled ones.

    If defaults.use_defaults is true, apply default filters to all countries
    unless they explicitly override them.
    """
    config_file = Path(__file__).parent.parent.parent / "config" / "countries.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Countries config file not found: {config_file}")

    with open(config_file) as f:
        data = yaml.safe_load(f)

    # Get global defaults if enabled
    defaults_config = data.get("defaults", {})
    use_defaults = defaults_config.get("use_defaults", False)
    default_severities = defaults_config.get("severities", [])
    default_certainties = defaults_config.get("certainties", [])
    default_urgencies = defaults_config.get("urgencies", [])

    countries = []
    for code, config in data.get("countries", {}).items():
        if config.get("enabled", False):
            # Use defaults if enabled, otherwise use country-specific or empty
            severities = default_severities if use_defaults else config.get("severities", [])
            certainties = default_certainties if use_defaults else config.get("certainties", [])
            urgencies = default_urgencies if use_defaults else config.get("urgencies", [])

            countries.append(
                Country(
                    code=code,
                    name=config["name"],
                    feed_url=config["feed_url"],
                    severities=severities,
                    certainties=certainties,
                    urgencies=urgencies,
                )
            )

    return countries


COUNTRIES: list[Country] = _load_countries_from_yaml()


class Settings(BaseSettings):
    """Runtime configuration, populated from environment variables.

    Attributes:
        log_level: Root logging level, e.g. "INFO" or "DEBUG".
        http_timeout_seconds: Per-request timeout for feed HTTP calls.
        max_concurrency: Max number of feeds fetched at once.
        database_url: Postgres connection string (used from the DB slice onward).
        timezone_name: Default application timezone; CET is used locally by default.
        smtp_host: SMTP host used for summary emails.
        smtp_port: SMTP port used for summary emails.
        smtp_username: Optional SMTP username.
        smtp_password: Optional SMTP password.
        email_from: Sender address used for summary emails.
        email_to: Recipient address used for summary emails.
        smtp_enabled: Whether to send summary emails.

    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="METEOALARM_")

    log_level: str = "INFO"
    http_timeout_seconds: float = 10.0
    max_concurrency: int = 5
    database_url: str = "postgresql+asyncpg://meteoalarm:meteoalarm@localhost:5432/meteoalarm"
    timezone_name: str = "Europe/Warsaw"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str = "meteoalarm@localhost"
    email_to: str = "ops@localhost"
    smtp_enabled: bool = True

    @property
    def timezone(self) -> ZoneInfo:
        """Return the configured timezone as a ZoneInfo instance.

        This automatically handles winter/summer offset changes (CET/CEST) for
        the configured region, instead of using a fixed UTC offset.
        """
        return ZoneInfo(self.timezone_name)


def get_settings() -> Settings:
    """Return a freshly loaded :class:`Settings` instance.

    A plain function (rather than a module-level singleton) keeps this
    easy to override in tests via monkeypatching or dependency injection.
    """
    return Settings()
