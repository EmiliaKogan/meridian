import sys

from meridian.ingest_to_bronze.ingest import (
    download_source_zip,
    find_latest_csvs_in_zip,
    find_source_zip,
    save_bronze_csvs,
)
from meridian.parsing import parse_dataset_market, parse_month


def run(job: str, month: str) -> None:
    """Run Bronze ingestion for one job and month."""
    _, market = parse_dataset_market(job)
    data_window = parse_month(month)
    source_zip, last_modified = find_source_zip(market, data_window)
    zip_path = download_source_zip(source_zip)
    try:
        csv_paths = find_latest_csvs_in_zip(zip_path, market, data_window)
        save_bronze_csvs(
            zip_path, csv_paths, market, data_window,
            source_key=source_zip, last_modified=last_modified,
        )
    finally:
        zip_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
