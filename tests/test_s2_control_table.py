from meridian.operational.control import record_job_attempt


GOOD = {"layer": "silver", "job": "trips:jc", "market": "jc", "window": "2021-01",}


def _record(conn, status: str) -> None:
    record_job_attempt(conn, GOOD["layer"], GOOD["job"], GOOD["market"], GOOD["window"], status,)


def test_successful_job_attempt_is_recorded(conn):
    _record(conn, "SUCCESS")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT layer, job, market, load_window, status
            FROM control_table
            """
        )
        row = cur.fetchone()

    assert row == (
        GOOD["layer"],
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )


def test_failed_job_attempt_is_recorded(conn):
    _record(conn, "FAILED")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status
            FROM control_table
            """
        )
        status = cur.fetchone()[0]

    assert status == "FAILED"


def test_same_job_can_be_recorded_in_different_layers(conn):
    record_job_attempt(
        conn,
        "bronze",
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )
    _record(conn, "SUCCESS")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT layer
            FROM control_table
            ORDER BY id
            """
        )
        layers = [row[0] for row in cur.fetchall()]

    assert layers == ["bronze", "silver"]


def test_recording_same_attempt_twice_keeps_both(conn):
    _record(conn, "SUCCESS")
    _record(conn, "SUCCESS")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM control_table
            """
        )
        count = cur.fetchone()[0]

    assert count == 2


def test_failed_then_successful_attempt_keeps_both(conn):
    _record(conn, "FAILED")
    _record(conn, "SUCCESS")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status
            FROM control_table
            ORDER BY id
            """
        )
        statuses = [row[0] for row in cur.fetchall()]

    assert statuses == ["FAILED", "SUCCESS"]


def test_job_attempt_has_finished_at(conn):
    _record(conn, "SUCCESS")
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT finished_at
            FROM control_table
            """
        )
        finished_at = cur.fetchone()[0]

    assert finished_at is not None