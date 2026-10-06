from meridian.ingest_to_bronze.ingest import find_source_zip


def is_published(market: str, month: str) -> bool:
    """Return whether source data exists for the market and month."""
    try:
        find_source_zip(market.upper(), month)
    except ValueError as error:
        if str(error).startswith("No source ZIP found"):
            return False
        raise

    return True