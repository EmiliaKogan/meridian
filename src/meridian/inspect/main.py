import csv
import json
import os
import sys
from pathlib import Path

import psycopg


def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()

    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def inspect_bronze(market: str, data_window: str) -> None:
    year, month = data_window.split("-")
    bronze_dir = Path("/data/bronze") / market / year / month

    csv_files = sorted(bronze_dir.glob("*.csv"))

    total_rows = 0

    for csv_file in csv_files:
        with csv_file.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            next(reader, None)

            total_rows += sum(1 for _ in reader)

    result = {
        "layer": "bronze",
        "job": f"trips:{market.lower()}",
        "window": data_window,
        "objects": len(csv_files),
        "rows": total_rows,
    }

    print(json.dumps(result))


def inspect_silver(market: str, data_window: str) -> None:
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM silver_rides
                WHERE market = %s
                  AND data_window = %s
                """,
                (market, data_window),
            )

            rows = cur.fetchone()[0]

            cur.execute(
                """
                SELECT reason, COUNT(*)
                FROM silver_rejects
                WHERE market = %s
                  AND data_window = %s
                GROUP BY reason
                ORDER BY reason
                """,
                (market, data_window),
            )

            reason_rows = cur.fetchall()

    reasons = {
        reason: count
        for reason, count in reason_rows
    }

    result = {
        "layer": "silver",
        "job": f"trips:{market.lower()}",
        "window": data_window,
        "rows": rows,
        "rejects": sum(reasons.values()),
        "reasons": reasons,
    }

    print(json.dumps(result))


def main() -> None:
    layer = sys.argv[1]
    _, market = parse_dataset_market(sys.argv[2])
    data_window = sys.argv[3]

    if layer == "bronze":
        inspect_bronze(market, data_window)
    elif layer == "silver":
        inspect_silver(market, data_window)
    else:
        raise ValueError(f"Unknown layer: {layer}")


if __name__ == "__main__":
    main()