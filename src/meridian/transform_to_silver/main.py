import os
import sys

import psycopg

from meridian.parsing import parse_dataset_market, parse_month
from meridian.paths import data_window_dir
from meridian.transform_to_silver.database import (
    delete_window,
    insert_silver_rejects,
    insert_silver_rides,
)
from meridian.transform_to_silver.transform import transform_file


def run(job: str, month: str) -> None:
    """Load one Bronze window into Silver."""
    _, market = parse_dataset_market(job)
    data_window = parse_month(month)
    bronze_dir = data_window_dir(market, data_window)
    csv_files = sorted(bronze_dir.glob("*.csv"))
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        delete_window(conn, market, data_window)
        for csv_file in csv_files:
            valid_rows, reject_rows = transform_file(csv_file, market, data_window)
            insert_silver_rides(conn, valid_rows)
            insert_silver_rejects(conn, reject_rows)
        conn.commit()


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])