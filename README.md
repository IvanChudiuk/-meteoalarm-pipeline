# MeteoAlarm Pipeline

An async ETL pipeline that fetches severe weather alerts (rain, wind,
thunderstorm, snow, etc.) from [MeteoAlarm](https://meteoalarm.org)'s public
[ATOM/CAP feeds](https://feeds.meteoalarm.org/) for multiple European countries,
validates and normalises them, and prepares them for querying and reporting.

## Table of contents

- [Overview](#overview)
- [Quick start](#quick-start)
- [Local development](#local-development-without-docker)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Linting and formatting](#linting-and-formatting)
- [Testing](#testing)
- [Adding a country](#adding-a-country)
- [Roadmap](#roadmap)

## Overview

This project is the first working slice of the pipeline: **fetch → parse → validate → print → email**.
It fetches alerts for the configured countries concurrently, parses CAP/ATOM XML
feeds, validates the data, prints a grouped summary to stdout, and sends an HTML
email summary with an alert table.

Malformed entries are logged as warnings and skipped instead of crashing the feed.

All times in the email are displayed in **Europe/Warsaw timezone** with automatic DST handling (CET/CEST).

## Quick start

### Requirements

- Docker Engine
- Docker Compose

### Run

Build the app image and start the app with MailHog:

```bash
docker compose up --build -d
```

The app container is a one-shot job: it runs the full pipeline (fetch → parse →
validate → print → email) and then exits, while MailHog keeps running. That is
why `docker compose ps` shows the app as exited; use `docker compose ps -a` to
see it.

View the pipeline output:

```bash
docker compose logs -f app
```

Open http://localhost:8025 to inspect the summary email in MailHog. Application
logs are also kept in the repository's `logs/` directory.

To run the pipeline again, rebuild if you changed code or config, then start it:

```bash
docker compose up --build
```

Stop and remove the containers when finished:

```bash
docker compose down
```

**Logging:** All logs are written to stdout and `logs/meteoalarm.log`, with daily
rotation (keeps 7 days of logs and rotates at midnight).

## Local development (without Docker)

Requires Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

To receive the summary email locally, start MailHog first:

```bash
docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

Then run the pipeline:

```bash
python -m meteoalarm_pipeline.main
```

Without a running SMTP server the app does not crash; it logs a warning instead.

## Architecture

The codebase follows a clean/hexagonal layering so business rules stay independent
of any specific transport, storage, or notification technology:

```text
meteoalarm-pipeline/
├── Dockerfile                          # Builds the Python application image
├── docker-compose.yml                  # Runs the app with MailHog
├── .dockerignore                       # Excludes local/dev files from image builds
├── config/
│   └── countries.yaml                  # Enabled countries and alert filters
├── src/meteoalarm_pipeline/
│   ├── application/
│   │   ├── fetch_alerts.py              # Fetch/parse orchestration and filtering
│   │   └── interfaces.py                # Ports used by the application layer
│   ├── domain/
│   │   ├── enums.py                     # Domain enumerations
│   │   └── models.py                    # Country and alert models
│   ├── infrastructure/
│   │   ├── db/                          # Reserved for future persistence adapters
│   │   ├── email/
│   │   │   ├── summary_notifier.py      # SMTP email delivery
│   │   │   └── summary_email.html.jinja2 # Email template
│   │   └── feeds/
│   │       ├── cap_atom_parser.py       # CAP/ATOM parsing and validation
│   │       └── http_client.py           # Async feed HTTP client
│   ├── config.py                        # Environment settings and country loading
│   ├── logging_config.py                # Console and rotating file logging
│   └── main.py                          # Composition root and entrypoint
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── pyproject.toml                       # Project metadata and dependencies
```

The application layer depends only on domain models and the protocol interfaces
inside the application package. That keeps the business logic independent from
concrete HTTP clients, parsers, or future storage implementations.

## Configuration

Runtime settings (log level, timeouts, SMTP settings, etc.) are environment
variables with a `METEOALARM_` prefix. See `src/meteoalarm_pipeline/config.py`
for the full list and default values.

### Email configuration

The app sends summary emails via SMTP with the following defaults:

- **Timezone:** Europe/Warsaw (automatic DST handling: CET in winter, CEST in summer)
- **SMTP host:** localhost:1025 (local MailHog for development)
- **Email from:** meteoalarm@localhost
- **Email to:** ops@localhost

When running under Docker Compose, the SMTP host is overridden to `mailhog`,
because inside a container `localhost` refers to the container itself. The
`localhost:1025` default applies when you run the app directly on your machine.

The email includes a formatted HTML table with columns:

- **alert_color** (with colored badges: Red, Orange, Yellow, Green)
- **alert_type** (event description)
- **country_name** (e.g. Spain, France)
- **zone_name** (affected area)
- **alert_start** (when the alert becomes effective, in local timezone)
- **alert_expires** (when the alert expires, in local timezone)

### Countries and alert filters

Countries are configured in `config/countries.yaml`. Each country can be:

- enabled or disabled via the `enabled` flag
- filtered by severity: green, yellow, orange, red
- filtered by certainty: observed, likely, possible, unlikely, unknown
- filtered by urgency: immediate, expected, future, past, unknown

#### Global defaults

Use the `defaults` section to apply filters to all enabled countries at once:

```yaml
defaults:
  use_defaults: true
  severities: [orange, red]
  certainties: [observed, likely]
  urgencies: [immediate, expected]

countries:
  spain:
    enabled: true
    name: Spain
    feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain
```

When `use_defaults: true`, the default filters override each country's individual
settings. Set `use_defaults: false` to use per-country filters instead.

#### Per-country filters

```yaml
defaults:
  use_defaults: false

countries:
  spain:
    enabled: true
    name: Spain
    feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain
    severities: [orange, red]
    certainties: [observed, likely]
    urgencies: [immediate, expected]
```

Leave filter lists empty to track all values for that filter.

## Linting and formatting

The project uses Ruff for linting and formatting. Run the checks before opening
a PR, either locally (inside your virtual environment) or in the container:

```bash
ruff format --check .
ruff format .
ruff check .
ruff check . --fix
```

```bash
docker compose run --rm app ruff check .
```

## Testing

Locally (inside your virtual environment):

```bash
pytest
```

Or in the container:

```bash
docker compose run --rm app pytest
```

The test suite covers:

- CAP/ATOM parser behaviour against a real trimmed XML sample, including a deliberately malformed entry
- fetch/parse orchestration logic and alert filtering using fakes instead of real network calls
- end-to-end flow validation from feed fetch to parsing and filtering
- email rendering and SMTP send behavior with timezone-aware alert times

## Adding a country

Add an entry to `config/countries.yaml` with the country's feed URL from
https://feeds.meteoalarm.org/. Set `enabled: true` to include it in the pipeline,
and optionally add severity, certainty, and urgency filters.

Example:

```yaml
new_country:
  enabled: true
  name: New Country
  feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-xxx
  severities: [green, yellow, orange, red]
  certainties: [observed, likely]
  urgencies: [immediate, expected]
```

If you run the pipeline with Docker, rebuild afterwards so the image picks up
the change: `docker compose up --build`.

## Roadmap

- [x] Docker image and Docker Compose setup for the app and MailHog
- [x] Fetch + parse + validate + print
- [x] Summary email via SMTP using MailHog in local dev and Jinja2 templates for alert summaries
- [ ] GitHub Actions CI (lint, type-check, test) and scheduled fetch workflow
- [ ] Postgres persistence via SQLAlchemy (async) + Alembic migrations and idempotent upsert by CAP identifier
- [ ] Add Postgres to the Docker Compose stack