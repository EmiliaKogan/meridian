import sys

from meridian.ingest_to_bronze.ingest import (
    download_source_zip,
    find_latest_csvs_in_zip,
    find_source_zip,
    save_bronze_csvs,
)


def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()

    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def main() -> None:
    """Run the Bronze ingestion job."""

    dataset, market = parse_dataset_market(sys.argv[1])
    data_window = sys.argv[2]

    print(f"Bronze ingestion started")
    print(f"Market: {market}")
    print(f"Window: {data_window}")

    source_zip = find_source_zip(market, data_window)
    print(f"Source ZIP: {source_zip}")

    zip_path = download_source_zip(source_zip)

    try:
        csv_paths = find_latest_csvs_in_zip(zip_path, market, data_window,)

        # for csv_path in csv_paths:
        #     print(f"Latest CSV: {csv_path}")

        save_bronze_csvs(zip_path, csv_paths, market, data_window,)
        print("Bronze ingestion completed")

    finally:
        zip_path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()


