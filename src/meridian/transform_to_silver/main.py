import sys
import csv
from pathlib import Path

from meridian.transform_to_silver.transform import transform_file


def conform_new(row: dict, market: str) -> dict:
    return {
        "market": market,
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "start_station_id": row["start_station_id"],
        "end_station_id": row["end_station_id"],
        "start_station_name": row["start_station_name"],
        "end_station_name": row["end_station_name"],
        "start_lat": row["start_lat"],
        "start_lng": row["start_lng"],
        "end_lat": row["end_lat"],
        "end_lng": row["end_lng"],
    }


def conform_old(row: dict) -> dict:
    return {
        "market": "NYC",
        "started_at": row["starttime"],
        "ended_at": row["stoptime"],
        "start_station_id": row["start station id"],
        "end_station_id": row["end station id"],
        "start_station_name": row["start station name"],
        "end_station_name": row["end station name"],
        "start_lat": row["start station latitude"],
        "start_lng": row["start station longitude"],
        "end_lat": row["end station latitude"],
        "end_lng": row["end station longitude"],
    }


def transform_file(csv_file: Path, market: str) -> None:
    with csv_file.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if "starttime" in row:
                conformed = conform_old(row)
            else:
                conformed = conform_new(row, market)

            print(conformed)



########################################################################

def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()

    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def main() -> None:
    _, market = parse_dataset_market(sys.argv[1])
    data_window = sys.argv[2]

    year, month = data_window.split("-")
    bronze_dir = Path("/data/bronze") / market / year / month
    csv_files = sorted(bronze_dir.glob("*.csv"))

    if not csv_files:
        raise ValueError(f"No Bronze CSV files found in {bronze_dir}")

    print("Silver transformation started")
    print(f"Market: {market}")
    print(f"Window: {data_window}")
    print(f"CSV files: {len(csv_files)}")

    for csv_file in csv_files:
        transform_file(csv_file, market)

    print("Silver transformation completed")


if __name__ == "__main__":
    main()