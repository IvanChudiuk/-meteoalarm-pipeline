# MeteoAlarm Pipeline

An async ETL pipeline that fetches severe weather alerts (rain, wind,
thunderstorm, snow, etc.) from [MeteoAlarm](https://meteoalarm.org)'s public
[ATOM/CAP feeds](https://feeds.meteoalarm.org/) for multiple European countries,
validates and normalises them, and prepares them for querying and reporting.

## Table of contents

- [Overview](#overview)
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Running the pipeline](#running-the-pipeline)
- [Configuration](#configuration)
- [Linting and formatting](#linting-and-formatting)
- [Testing](#testing)
- [Adding a country](#adding-a-country)
- [Roadmap](#roadmap)

## Overview

This project is the first working slice of the pipeline: **fetch → parse → validate → print**.
It currently fetches alerts for configured countries, parses CAP/ATOM XML feeds,
validates the data, and prints a grouped summary to stdout.

Malformed entries are logged as warnings and skipped instead of crashing the feed.

## Quick start

### Requirements

- Python 3.12+

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run

```bash
python -m meteoalarm_pipeline.main
```

This fetches the live feeds for all configured countries concurrently, parses and
validates all entries, and prints a grouped summary to stdout.

**Logging:** All logs are written to stdout and `logs/meteoalarm.log`, with daily
rotation (keeps 7 days of logs and rotates at midnight).

## Architecture

The codebase follows a clean/hexagonal layering so business rules stay independent
of any specific transport, storage, or notification technology:

```text
src/meteoalarm_pipeline/
├── domain/            # Pure models & enums - no I/O, no framework dependency
├── application/       # Use cases + protocol interfaces + alert filtering
├── infrastructure/    # Concrete implementations of those ports
│   └── feeds/         # HTTP fetcher + CAP/ATOM parser
├── config.py          # Typed settings (env vars) + country registry
├── logging_config.py  # Centralised logging setup (console + daily rotating file logs)
├── main.py            # Composition root / entrypoint
└── __init__.py
```

The application layer depends only on domain models and the protocol interfaces
inside the application package. That keeps the business logic independent from
concrete HTTP clients, parsers, or future storage implementations.

## Running the pipeline

Use the project entrypoint to run the full feed pipeline locally:

```bash
python -m meteoalarm_pipeline.main
```

This uses the configured countries in `config/countries.yaml`, fetches their feeds,
parses each alert, and prints a human-readable summary.

## Configuration

All runtime settings (log level, timeouts, database URL, etc.) are environment
variables with a `METEOALARM_` prefix. See `.env.example` for the full list and
`src/meteoalarm_pipeline/config.py` for the default values.

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

The project uses Ruff for linting and formatting. Run the checks locally before
opening a PR:

```bash
ruff format --check .
ruff format .
ruff check .
ruff check . --fix
```

## Testing

```bash
pytest
```

The test suite covers:

- CAP/ATOM parser behaviour against a real trimmed XML sample, including a deliberately malformed entry
- fetch/parse orchestration logic and alert filtering using fakes instead of real network calls
- end-to-end flow validation from feed fetch to parsing and filtering

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

## Roadmap

- [x] Fetch + parse + validate + print
- [ ] Postgres persistence via SQLAlchemy (async) + Alembic migrations and idempotent upsert by CAP identifier
- [ ] Scheduled summary email (SMTP) for new or severe alerts
- [ ] Dockerfile + docker-compose (app + Postgres)
- [ ] GitHub Actions CI (lint, type-check, test) and scheduled fetch workflow
