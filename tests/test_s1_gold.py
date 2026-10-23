
import json
import subprocess

import pytest

from meridian.report.database import get_daily_station_trips
from meridian.transform_to_gold.database import (
    delete_day,
    insert_date,
    insert_stations,
    insert_events,
)
from meridian.transform_to_gold.transform import build_date_row
from datetime import date


GOOD = {
    "market": "jc",
    "station": "JC115",
    "day": "2026-06-02",
    "departures": 216,
    "arrivals": 209,
}


def test_gold_station_counts(conn):
    """Gold calculates departures and arrivals from Silver."""
    conn.execute("""
        INSERT INTO silver_rides (
            market, data_window, started_at, ended_at,
            start_station_id, end_station_id
        )
        VALUES
            ('JC', '2026-06', '2026-06-02 08:00+00',
             '2026-06-02 08:15+00', 'JC115', 'JC116'),
            ('JC', '2026-06', '2026-06-02 09:00+00',
             '2026-06-02 09:15+00', 'JC117', 'JC115')
    """)

    target = GOOD["day"]
    delete_day(conn, target)
    insert_date(conn, build_date_row(date.fromisoformat(target)))
    insert_stations(conn, target)
    insert_events(conn, target)

    departures, arrivals = get_daily_station_trips(
        conn, "JC", "JC115", 20260602
    )

    assert (departures, arrivals) == (1, 1)


@pytest.mark.skip(reason="Requires real JC June 2026 data in Docker Compose")
def test_gold_jc115_regression():
    """Gold must preserve the expected station-day counts."""
    result = subprocess.run(
        [
            "just", "report", "daily-station-trips",
            GOOD["market"], GOOD["station"], GOOD["day"],
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout.splitlines()[-1])
    assert actual == GOOD
