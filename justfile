# Start the Meridian stack.
up:
    docker compose up -d

# Stop the Meridian stack.
down:
    docker compose down

# Run a Meridian job.
run *args:
    just {{args}}

# Run the Bronze ingestion job for a specific market and data window.
ingest-to-bronze dataset_market window:
    docker compose run --rm app uv run python -m meridian.ingest_to_bronze.main {{dataset_market}} {{window}}

# Transform Bronze data into Silver for a specific dataset and data window.
transform-to-silver dataset_market window:
    docker compose run --rm app uv run python -m meridian.transform_to_silver.main {{dataset_market}} {{window}}

# Transform Silver data into Gold for a specific dataset and date.
transform-to-gold dataset date:
    docker compose run --rm app uv run python -m meridian.transform_to_gold.main {{dataset}} {{date}}

# Inspect Bronze or Silver data for a specific dataset and data window.
inspect layer dataset_market window:
    docker compose run --rm app uv run python -m meridian.inspect.main {{layer}} {{dataset_market}} {{window}}

# Report daily station departures and arrivals.
report report_type market station_id date:
    docker compose run --rm app uv run python -m meridian.report.main {{report_type}} {{market}} {{station_id}} {{date}}


