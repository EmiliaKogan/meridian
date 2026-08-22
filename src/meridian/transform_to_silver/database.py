import psycopg


BATCH_SIZE = 1_000


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


def delete_window(conn: psycopg.Connection, market: str, data_window: str,) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM silver_rides
            WHERE market = %s
              AND data_window = %s
            """,
            (market, data_window),
        )

        cur.execute(
            """
            DELETE FROM silver_rejects
            WHERE market = %s
              AND data_window = %s
            """,
            (market, data_window),
        )


def insert_silver_rides(
    conn: psycopg.Connection,
    rows: list[dict],
) -> int:
    query = """
        INSERT INTO silver_rides (
            market,
            data_window,
            started_at,
            ended_at,
            start_station_id,
            end_station_id,
            start_station_name,
            end_station_name,
            start_lat,
            start_lng,
            end_lat,
            end_lng
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
    """

    values = [
        (
            row["market"],
            row["data_window"],
            row["started_at"],
            row["ended_at"],
            row["start_station_id"],
            row["end_station_id"],
            row["start_station_name"],
            row["end_station_name"],
            row["start_lat"],
            row["start_lng"],
            row["end_lat"],
            row["end_lng"],
        )
        for row in rows
    ]

    return _insert(conn, query, values)


def insert_silver_rejects(
    conn: psycopg.Connection,
    rows: list[dict],
) -> int:
    query = """
        INSERT INTO silver_rejects (
            market,
            data_window,
            started_at,
            ended_at,
            start_station_id,
            end_station_id,
            start_station_name,
            end_station_name,
            start_lat,
            start_lng,
            end_lat,
            end_lng,
            reason
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
    """

    values = [
        (
            row["market"],
            row["data_window"],
            row["started_at"],
            row["ended_at"],
            row["start_station_id"],
            row["end_station_id"],
            row["start_station_name"],
            row["end_station_name"],
            row["start_lat"],
            row["start_lng"],
            row["end_lat"],
            row["end_lng"],
            row["reason"],
        )
        for row in rows
    ]

    return _insert(conn, query, values)