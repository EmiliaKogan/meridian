# Run the Bronze ingestion job for a specific market and data window.
ingest-to-bronze dataset_market window:
    docker compose run --rm app uv run python -m meridian.ingest_to_bronze.main {{dataset_market}} {{window}}

# Transform Bronze data into Silver for a specific dataset and data window.
transform-to-silver dataset_market window:
    docker compose run --rm app uv run python -m meridian.transform_to_silver.main {{dataset_market}} {{window}}