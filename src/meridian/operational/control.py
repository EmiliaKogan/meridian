import psycopg


def record_job_attempt(conn: psycopg.Connection, layer: str, job: str, market: str, load_window: str, status: str,) -> None:
    conn.execute(
        """
        INSERT INTO control_table (
            layer,
            job,
            market,
            load_window,
            status
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            layer,
            job,
            market,
            load_window,
            status,
        ),
    )