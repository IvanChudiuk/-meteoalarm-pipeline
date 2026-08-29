# MeteoAlarm Pipeline

An async ETL pipeline that fetches severe weather alerts (rain, wind, thunderstorm,
snow, etc.) from [MeteoAlarm](https://meteoalarm.org)'s public [ATOM/CAP feeds](https://feeds.meteoalarm.org/) for
multiple European countries, validates and normalises them, and stores them for
querying and summary reporting.

## Current status

This is the first working slice: **fetch → parse → validate → print**.
Database persistence and email summaries are planned next (see Roadmap).

## Architecture

The codebase follows a clean/hexagonal layering so business rules stay
independent of any specific transport, storage, or notification technology:

```
src/meteoalarm_pipeline/
├── domain/            # Pure models & enums - no I/O, no framework dependency
├── application/        # Use cases + Protocol interfaces ("ports") + alert filtering
├── infrastructure/     # Concrete implementations of those ports
│   └── feeds/           # HTTP fetcher + CAP/ATOM parser
├── config.py            # Typed settings (env vars) + country registry
├── logging_config.py     # Centralised logging setup (console + daily rotating file logs)
└── main.py                # Composition root / entrypoint
```

`application` code depends only on `domain` models and the `Protocol`
interfaces in `application/interfaces.py` - never on a concrete class in
`infrastructure`. That means swapping the HTTP client, the parser, or (later)
the database, never touches the orchestration logic, and unit tests use plain
fakes instead of mocking a library.

## Requirements

- Python 3.12+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
python -m meteoalarm_pipeline.main
```

This fetches the live feeds for all configured countries concurrently, parses
and validates every entry, and prints a grouped summary to stdout. Malformed
entries are logged as warnings and skipped rather than crashing the run.

**Logging:** All logs are written to both stdout and `logs/meteoalarm.log`, with 
daily rotation (keeps 7 days of logs, rotates at midnight).

## Test

```bash
pytest
```

Unit tests cover:
- CAP/ATOM parser (against a real trimmed sample feed, including a deliberately malformed entry)
- Fetch/parse orchestration logic and alert filtering (against fakes - no real network calls in the unit suite)
- End-to-end pipeline tests covering the complete flow from feed fetch through parsing and filtering

## Configuration

All runtime settings (log level, timeouts, database URL, etc.) are environment 
variables with a `METEOALARM_` prefix; see `.env.example` for the full list and 
`src/meteoalarm_pipeline/config.py` for defaults.

### Countries and Alert Filters

Countries are configured in `config/countries.yaml`. Each country can be:
- **Enabled/disabled** via the `enabled` flag
- **Filtered by severity** (green, yellow, orange, red)
- **Filtered by certainty** (observed, likely, possible, unlikely, unknown)
- **Filtered by urgency** (immediate, expected, future, past, unknown)

#### Global Defaults

Use the `defaults` section to apply filters to all enabled countries at once:

```yaml
defaults:
  use_defaults: true  # Enable to apply defaults to ALL countries
  severities: [orange, red]        # Override all individual country settings
  certainties: [observed, likely]
  urgencies: [immediate, expected]

countries:
  spain:
    enabled: true
    name: Spain
    feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain
    # When use_defaults=true, the above default filters apply (orange+red only)
```

When `use_defaults: true`, the default filters override each country's individual 
settings. Set `use_defaults: false` to use per-country filters instead.

#### Per-Country Filters (when defaults disabled)

```yaml
defaults:
  use_defaults: false  # Use individual country settings

countries:
  spain:
    enabled: true
    name: Spain
    feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain
    severities: [orange, red]        # Only track severe/extreme alerts
    certainties: [observed, likely]  # Only high-confidence forecasts
    urgencies: [immediate, expected] # Only urgent/expected action needed
```

Leave filter lists empty to track all values for that filter.

## Adding a country

Add an entry to `config/countries.yaml` with the country's feed URL from 
https://feeds.meteoalarm.org/. Set `enabled: true` to include it in the pipeline, 
and optionally add severity/certainty/urgency filters.

Example:
```yaml
  new_country:
    enabled: true
    name: New Country
    feed_url: https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-xxx
    severities: [green, yellow, orange, red]  # Optional
    certainties: [observed, likely]           # Optional
    urgencies: [immediate, expected]          # Optional
```

## Roadmap

- [x] Fetch + parse + validate + print (this slice)
- [ ] Postgres persistence via SQLAlchemy (async) + Alembic migrations, idempotent upsert by CAP identifier
- [ ] Scheduled summary email (SMTP) for new/severe alerts
- [ ] Dockerfile + docker-compose (app + Postgres)
- [ ] GitHub Actions CI (lint, type-check, test) and scheduled fetch workflow
