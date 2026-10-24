# Meridian

Meridian is a bike-share data engineering platform built with Python, PostgreSQL, Docker Compose, and Apache Airflow.

The project processes monthly trip data for Jersey City (JC) and New York City (NYC) through a Bronze → Silver → Gold pipeline.

## Architecture

**Stage 1 — Data processing**

- **Bronze:** Ingests source trip data.
- **Silver:** Validates and transforms trips into structured PostgreSQL records.
- **Gold:** Builds daily station-level departure and arrival events.
- Provides inspection and reporting commands.

**Stage 2 — Orchestration**

- Airflow DAGs schedule monthly processing for each market.
- An operational control table records job attempts and outcomes.
- Coverage is calculated dynamically using completed months, gaps, and a watermark.
- Supports manual runs, backfills, retries, and idempotent processing.
- Gold processes individual days and retries failed days.

See [notes.md](notes.md) for architectural decisions and implementation details.

## Requirements

- Docker with Docker Compose
- Python 3.14+
- `uv`
- `just`

## Getting Started

From the project root:

```bash
just up
```

This builds the application and Airflow images, starts PostgreSQL and Airflow, and applies database migrations.

Airflow UI: http://localhost:8080

Schedules are initially paused.

## Running the Pipeline

Enable or disable monthly scheduling:

```bash
just schedule jc on
just schedule jc off
just schedule nyc on
```

Run the next required month:

```bash
just run pipeline jc
```

Run a specific month:

```bash
just run pipeline jc 2026-06
```

Run a month range (backfill):

```bash
just run pipeline jc 2021-01 2021-02
```

The pipeline client waits for the Airflow operation to complete and reports failures.

## Inspecting Progress

View pipeline coverage:

```bash
just inspect coverage trips:jc
just inspect coverage trips:nyc
```

Coverage includes:

- `earliest` — first supported month
- `watermark` — last consecutively completed month
- `complete` — number of completed months
- `gaps` — incomplete months before later completed months
- `next` — earliest incomplete month

Inspect operational runs:

```bash
just inspect runs jc
just inspect runs nyc
```

## Gold Report

Example station-day report:

```bash
just report daily-station-trips jc JC115 2026-06-02
```

Expected result after loading the JC June 2026 data:

```json
{
  "market": "jc",
  "station": "JC115",
  "day": "2026-06-02",
  "departures": 216,
  "arrivals": 209
}
```

## Testing

Run the automated test suite:

```bash
uv run pytest -q
```

Tests use an isolated PostgreSQL instance through Testcontainers.

Docker lifecycle tests in `test_infrastructure.py` are skipped by default because they start and stop Docker Compose services and may remove persistent volumes.

## Supported Markets

| Market | Job | Earliest month |
|---|---|---|
| Jersey City | `trips:jc` | 2021-01 |
| New York City | `trips:nyc` | 2026-01 |

## Shutdown

**Warning:** The current `just down` command runs `docker compose down -v` and deletes persistent Docker volumes, including database data.

Use it only when resetting the environment is intended.

## Additional Documentation

See [notes.md](notes.md) for the Stage 2 architecture, control-table semantics, coverage rules, orchestration responsibilities, and retry behavior.