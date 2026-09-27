import psycopg


def record_job_attempt(conn: psycopg.Connection, job: str, market: str, load_window: str, status: str,) -> None:
    conn.execute(
        """
        INSERT INTO control_table (
            job,
            market,
            load_window,
            status
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            job,
            market,
            load_window,
            status,
        ),
    )