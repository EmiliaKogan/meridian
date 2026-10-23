
import psycopg


INSERT_DATE_SQL = """
    INSERT INTO dim_date (date_key, date, year, month, day)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (date_key) DO NOTHING
"""

INSERT_STATIONS_SQL = """
    INSERT INTO dim_station (market, station_id, station_name)
    SELECT DISTINCT market, station_id, station_name
    FROM (
        SELECT market, start_station_id AS station_id,
               start_station_name AS station_name
        FROM silver_rides
        WHERE started_at::date = %s

        UNION

        SELECT market, end_station_id AS station_id,
               end_station_name AS station_name
        FROM silver_rides
        WHERE ended_at::date = %s
    ) stations
    WHERE station_id IS NOT NULL
    ON CONFLICT (market, station_id) DO NOTHING
"""

INSERT_EVENTS_SQL = """
    INSERT INTO fact_events (
        ride_id, market, event_type, event_timestamp,
        station_id, date_key
    )
    SELECT ride_id, market, 'departure', started_at,
           start_station_id, %s
    FROM silver_rides
    WHERE started_at::date = %s

    UNION ALL

    SELECT ride_id, market, 'arrival', ended_at,
           end_station_id, %s
    FROM silver_rides
    WHERE ended_at::date = %s
"""


def delete_day(conn: psycopg.Connection, target_date: str) -> None:
    date_key = int(target_date.replace("-", ""))
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM fact_events WHERE date_key = %s",
            (date_key,),
        )


def insert_date(conn: psycopg.Connection, date_row: dict) -> None:
    values = (
        date_row["date_key"],
        date_row["date"],
        date_row["year"],
        date_row["month"],
        date_row["day"],
    )
    with conn.cursor() as cur:
        cur.execute(INSERT_DATE_SQL, values)


def insert_stations(conn: psycopg.Connection, target_date: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            INSERT_STATIONS_SQL,
            (target_date, target_date),
        )


def insert_events(conn: psycopg.Connection, target_date: str) -> int:
    date_key = int(target_date.replace("-", ""))
    with conn.cursor() as cur:
        cur.execute(
            INSERT_EVENTS_SQL,
            (date_key, target_date, date_key, target_date),
        )
        return cur.rowcount
