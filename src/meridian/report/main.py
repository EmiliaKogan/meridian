import json
import os
import sys

import psycopg

from meridian.report.database import get_daily_station_trips


def main() -> None:
    report_type, market, station_id, target_date = sys.argv[1:5]

    if report_type != "daily-station-trips":
        raise ValueError(f"Unknown report: {report_type}")

    date_key = int(target_date.replace("-", ""))

    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        departures, arrivals = get_daily_station_trips(
            conn,
            market.upper(),
            station_id,
            date_key,
        )

    result = {
        "market": market,
        "station": station_id,
        "day": target_date,
        "departures": departures,
        "arrivals": arrivals,}

    print(json.dumps(result))


if __name__ == "__main__":
    main()