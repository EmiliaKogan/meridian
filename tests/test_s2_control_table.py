from meridian.operational.control import record_job_attempt


GOOD = {
    "job": "trips:jc",
    "market": "jc",
    "window": "2021-01",
}


def test_successful_job_attempt_is_recorded(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT job, market, load_window, status
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        row = cur.fetchone()

    assert row == (
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )


def test_failed_job_attempt_is_recorded(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "FAILED",
    )

    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT job, market, load_window, status
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        row = cur.fetchone()

    assert row == (
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "FAILED",
    )


def test_recording_same_job_attempt_twice_creates_two_records(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "FAILED",
    )
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        count = cur.fetchone()[0]

    assert count == 2


def test_job_attempt_has_finished_at(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT finished_at
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        finished_at = cur.fetchone()[0]

    assert finished_at is not None


def test_failed_then_successful_attempt_keeps_both_records(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "FAILED",
    )
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            ORDER BY id
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        statuses = [row[0] for row in cur.fetchall()]

    assert statuses == ["FAILED", "SUCCESS"]