
import psycopg
from psycopg.types.json import Jsonb


BATCH_SIZE = 1_000

RIDE_FIELDS = (
    "market", "data_window", "started_at", "ended_at",
    "start_station_id", "end_station_id",
    "start_station_name", "end_station_name",
    "start_lat", "start_lng", "end_lat", "end_lng",
)

RIDE_COLUMNS = ", ".join(RIDE_FIELDS)
REJECT_COLUMNS = RIDE_COLUMNS + ", reason, raw_row"

INSERT_RIDES_SQL = f"""
    INSERT INTO silver_rides ({RIDE_COLUMNS})
    VALUES ({", ".join(["%s"] * len(RIDE_FIELDS))})
"""

INSERT_REJECTS_SQL = f"""
    INSERT INTO silver_rejects ({REJECT_COLUMNS})
    VALUES ({", ".join(["%s"] * (len(RIDE_FIELDS) + 2))})
"""


def _insert(
    conn: psycopg.Connection,
    query: str,
    values: list[tuple],
    batch_size: int = BATCH_SIZE,
) -> int:
    inserted = 0
    for start in range(0, len(values), batch_size):
        batch = values[start:start + batch_size]
        with conn.cursor() as cur:
            cur.executemany(query, batch)
            inserted += cur.rowcount
    return inserted


def delete_window(
    conn: psycopg.Connection, market: str, data_window: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM silver_rides
            WHERE market = %s AND data_window = %s
            """,
            (market, data_window),
        )
        cur.execute(
            """
            DELETE FROM silver_rejects
            WHERE market = %s AND data_window = %s
            """,
            (market, data_window),
        )


def _ride_values(row: dict) -> tuple:
    return tuple(row[field] for field in RIDE_FIELDS)


def insert_silver_rides(
    conn: psycopg.Connection, rows: list[dict]
) -> int:
    values = [_ride_values(row) for row in rows]
    return _insert(conn, INSERT_RIDES_SQL, values)


def insert_silver_rejects(
    conn: psycopg.Connection, rows: list[dict]
) -> int:
    values = [
        (*_ride_values(row), row["reason"], Jsonb(row["raw_row"]))
        for row in rows
    ]
    return _insert(conn, INSERT_REJECTS_SQL, values)
