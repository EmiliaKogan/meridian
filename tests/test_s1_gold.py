
from datetime import date

from meridian.report.database import get_daily_station_trips
from meridian.transform_to_gold.database import (
    delete_day,
    insert_date,
    insert_stations,
    insert_events,
)
from meridian.transform_to_gold.transform import build_date_row


DAY = "2026-06-02"
NEXT_DAY = "2026-06-03"


def add_ride(conn, market, start, end, started, ended):
    conn.execute(
        """
        INSERT INTO silver_rides (
            market, data_window, started_at, ended_at,
            start_station_id, end_station_id
        )
        VALUES (%s, '2026-06', %s, %s, %s, %s)
        """,
        (market, started, ended, start, end),
    )


def build_gold(conn, target):
    delete_day(conn, target)
    insert_date(conn, build_date_row(date.fromisoformat(target)))
    insert_stations(conn, target)
    return insert_events(conn, target)


def counts(conn, market, station, target=DAY):
    return get_daily_station_trips(
        conn, market, station, int(target.replace("-", ""))
    )


def test_gold_station_counts(conn):
    """Gold counts departures and arrivals independently."""
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-02 08:00+00", "2026-06-02 08:15+00",
    )
    add_ride(
        conn, "JC", "JC117", "JC115",
        "2026-06-02 09:00+00", "2026-06-02 09:15+00",
    )

    assert build_gold(conn, DAY) == 4
    assert counts(conn, "JC", "JC115") == (1, 1)


def test_gold_multiple_departures_and_arrivals(conn):
    """Multiple rides are aggregated correctly."""
    for hour in (8, 9, 10):
        add_ride(
            conn, "JC", "JC115", "JC116",
            f"2026-06-02 {hour:02}:00+00",
            f"2026-06-02 {hour:02}:15+00",
        )

    add_ride(
        conn, "JC", "JC117", "JC115",
        "2026-06-02 11:00+00", "2026-06-02 11:15+00",
    )

    build_gold(conn, DAY)

    assert counts(conn, "JC", "JC115") == (3, 1)
    assert counts(conn, "JC", "JC116") == (0, 3)


def test_gold_separates_stations(conn):
    """Events are attributed to the correct station."""
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-02 08:00+00", "2026-06-02 08:15+00",
    )

    build_gold(conn, DAY)

    assert counts(conn, "JC", "JC115") == (1, 0)
    assert counts(conn, "JC", "JC116") == (0, 1)


def test_gold_separates_markets(conn):
    """Identical station IDs in different markets stay separate."""
    for market in ("JC", "NYC"):
        add_ride(
            conn, market, "S1", "S2",
            "2026-06-02 08:00+00", "2026-06-02 08:15+00",
        )

    build_gold(conn, DAY)

    assert counts(conn, "JC", "S1") == (1, 0)
    assert counts(conn, "NYC", "S1") == (1, 0)


def test_gold_handles_midnight_crossing(conn):
    """Departure and arrival belong to different calendar days."""
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-02 23:55+00", "2026-06-03 00:10+00",
    )

    assert build_gold(conn, DAY) == 1
    assert build_gold(conn, NEXT_DAY) == 1

    assert counts(conn, "JC", "JC115", DAY) == (1, 0)
    assert counts(conn, "JC", "JC116", NEXT_DAY) == (0, 1)


def test_gold_rerun_is_idempotent(conn):
    """Rebuilding a day does not duplicate its events."""
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-02 08:00+00", "2026-06-02 08:15+00",
    )

    first = build_gold(conn, DAY)
    second = build_gold(conn, DAY)

    assert first == second == 2
    assert counts(conn, "JC", "JC115") == (1, 0)
    assert counts(conn, "JC", "JC116") == (0, 1)


def test_gold_preserves_other_days(conn):
    """Rebuilding one day does not delete another day's events."""
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-02 08:00+00", "2026-06-02 08:15+00",
    )
    add_ride(
        conn, "JC", "JC115", "JC116",
        "2026-06-03 08:00+00", "2026-06-03 08:15+00",
    )

    build_gold(conn, DAY)
    build_gold(conn, NEXT_DAY)
    build_gold(conn, DAY)

    assert counts(conn, "JC", "JC115", DAY) == (1, 0)
    assert counts(conn, "JC", "JC115", NEXT_DAY) == (1, 0)
