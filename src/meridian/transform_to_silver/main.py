import os
import sys
from pathlib import Path

import psycopg

from meridian.transform_to_silver.transform import transform_file
from meridian.transform_to_silver.database import insert_silver_rides, insert_silver_rejects, delete_window


def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()

    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def main() -> None:
    dataset, market = parse_dataset_market(sys.argv[1])
    data_window = sys.argv[2]

    year, month = data_window.split("-")

    bronze_dir = Path("/data/bronze") / market / year / month

    csv_files = sorted(bronze_dir.glob("*.csv"))

    # print("Silver transformation started")
    # print(f"Market: {market}")
    # print(f"Window: {data_window}")

    database_url = os.environ["DATABASE_URL"]

    total_rows = 0
    total_rejects = 0

    with psycopg.connect(database_url) as conn:
        delete_window(conn, market, data_window)
        for csv_file in csv_files:
            valid_rows, reject_rows = transform_file(csv_file, market, data_window)

            inserted_rows = insert_silver_rides(conn, valid_rows)
            inserted_rejects = insert_silver_rejects(conn, reject_rows)

            total_rows += inserted_rows
            total_rejects += inserted_rejects

            print(
                f"{csv_file.name}: "
                f"{inserted_rows} valid rows, "
                f"{inserted_rejects} rejected rows"
            )

        conn.commit()

    # print(f"Total inserted rows: {total_rows}")
    # print(f"Total rejected rows: {total_rejects}")

    # print("Silver transformation completed")


if __name__ == "__main__":
    main()