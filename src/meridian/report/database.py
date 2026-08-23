import psycopg


def get_daily_station_trips(conn: psycopg.Connection,market: str,station_id: str,date_key: int,) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE event_type = 'departure'
                ) AS departures,
                COUNT(*) FILTER (
                    WHERE event_type = 'arrival'
                ) AS arrivals
            FROM fact_events
            WHERE market = %s
              AND station_id = %s
              AND date_key = %s
            """,
            (
                market,
                station_id,
                date_key,
            ),
        )

        row = cur.fetchone()

    return row[0], row[1]