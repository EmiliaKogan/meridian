# Start the Meridian stack.
up:
    docker compose up -d --wait postgres airflow-db
    docker compose run --rm app uv run alembic upgrade head
    docker compose up -d --wait airflow

# Stop the Meridian stack.
down:
    docker compose down

# Enable or disable the Airflow schedule for a market.
schedule market state:
    docker compose run --rm --no-deps app uv run python -m meridian.operational.schedule {{market}} {{state}}

# Run a Meridian job.
run *args:
    just {{args}}

# Run the Airflow pipeline for a market and optional month range.
pipeline market *windows:
    docker compose run --rm --no-deps app uv run python -m meridian.operational.pipeline {{market}} {{windows}}

# Run the Bronze ingestion job.
ingest-to-bronze job window:
    docker compose run --rm app uv run python -m meridian.ingest_to_bronze.main {{job}} {{window}}

# Transform Bronze data into Silver.
transform-to-silver job window:
    docker compose run --rm app uv run python -m meridian.transform_to_silver.main {{job}} {{window}}

# Transform Silver data into Gold.
transform-to-gold job window:
    docker compose run --rm app uv run python -m meridian.transform_to_gold.main {{job}} {{window}}

# Inspect Meridian data and operational state.
inspect *args:
    docker compose run --rm app uv run python -m meridian.inspect.main {{args}}

# Report daily station departures and arrivals.
report report_type market station day:
    docker compose run --rm app uv run python -m meridian.report.main {{report_type}} {{market}} {{station}} {{day}}


# # Run the Bronze ingestion job for a specific market and data window.
# ingest-to-bronze dataset_market window:
#     docker compose run --rm app uv run python -m meridian.ingest_to_bronze.main {{dataset_market}} {{window}}

# # Transform Bronze data into Silver for a specific dataset and data window.
# transform-to-silver dataset_market window:
#     docker compose run --rm app uv run python -m meridian.transform_to_silver.main {{dataset_market}} {{window}}

# # Transform Silver data into Gold for a specific dataset and date.
# transform-to-gold dataset date:
#     docker compose run --rm app uv run python -m meridian.transform_to_gold.main {{dataset}} {{date}}

# # Inspect Bronze or Silver data for a specific dataset and data window.
# inspect layer job window:
#     docker compose run --rm app uv run python -m meridian.inspect.main {{layer}} {{job}} {{window}}

# # Report daily station departures and arrivals.
# report report_type market station day:
#     docker compose run --rm app uv run python -m meridian.report.main {{report_type}} {{market}} {{station}} {{day}}


