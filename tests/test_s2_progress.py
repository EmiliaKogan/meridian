from datetime import date, timedelta

from meridian.operational.control import record_job_attempt
from meridian.operational.progress import progress


GOOD = {
    "job": "trips:jc",
    "market": "jc",
    "window": "2021-01",
}


def test_progress_when_no_loads_exist(conn):
    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_when_silver_is_loaded_but_gold_is_missing(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )
    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_when_month_has_silver_and_all_gold_days(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    day = date(2021, 1, 1)

    for _ in range(31):
        record_job_attempt(
            conn,
            "station-daily",
            GOOD["market"],
            day.isoformat(),
            "SUCCESS",
        )
        day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": "2021-01",
        "complete": 1,
        "gaps": [],
        "next": None,
    }


def test_progress_when_one_gold_day_is_missing(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    day = date(2021, 1, 1)

    for _ in range(30):
        record_job_attempt(
            conn,
            "station-daily",
            GOOD["market"],
            day.isoformat(),
            "SUCCESS",
        )
        day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_when_two_consecutive_months_are_complete(conn):
    for month, days in [("2021-01", 31), ("2021-02", 28)]:
        record_job_attempt(
            conn,
            GOOD["job"],
            GOOD["market"],
            month,
            "SUCCESS",
        )

        day = date.fromisoformat(f"{month}-01")

        for _ in range(days):
            record_job_attempt(
                conn,
                "station-daily",
                GOOD["market"],
                day.isoformat(),
                "SUCCESS",
            )
            day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": "2021-02",
        "complete": 2,
        "gaps": [],
        "next": None,
    }


def test_progress_when_there_is_a_gap_between_complete_months(conn):
    for month, days in [
        ("2021-01", 31),
        ("2021-02", 28),
        ("2021-04", 30),
    ]:
        record_job_attempt(
            conn,
            GOOD["job"],
            GOOD["market"],
            month,
            "SUCCESS",
        )

        day = date.fromisoformat(f"{month}-01")

        for _ in range(days):
            record_job_attempt(
                conn,
                "station-daily",
                GOOD["market"],
                day.isoformat(),
                "SUCCESS",
            )
            day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": "2021-02",
        "complete": 3,
        "gaps": ["2021-03"],
        "next": "2021-03",
    }


def test_progress_when_later_month_is_complete_but_earliest_is_not(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        "2021-02",
        "SUCCESS",
    )

    day = date(2021, 2, 1)

    for _ in range(28):
        record_job_attempt(
            conn,
            "station-daily",
            GOOD["market"],
            day.isoformat(),
            "SUCCESS",
        )
        day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 1,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_does_not_count_failed_gold_attempt(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    day = date(2021, 1, 1)

    for index in range(31):
        status = "FAILED" if index == 0 else "SUCCESS"

        record_job_attempt(
            conn,
            "station-daily",
            GOOD["market"],
            day.isoformat(),
            status,
        )
        day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_does_not_count_gold_finished_before_silver(conn):
    conn.execute(
        """
        INSERT INTO control_table (
            job,
            market,
            load_window,
            status,
            finished_at
        )
        VALUES (
            'station-daily',
            %s,
            '2021-01-01',
            'SUCCESS',
            CURRENT_TIMESTAMP - INTERVAL '1 hour'
        )
        """,
        (GOOD["market"],),
    )

    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["window"],
        "SUCCESS",
    )

    day = date(2021, 1, 2)

    for _ in range(30):
        record_job_attempt(
            conn,
            "station-daily",
            GOOD["market"],
            day.isoformat(),
            "SUCCESS",
        )
        day += timedelta(days=1)

    conn.commit()

    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": GOOD["window"],
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": GOOD["window"],
    }


def test_progress_uses_different_earliest_month_for_nyc(conn):
    result = progress(conn, "trips:nyc")

    assert result == {
        "job": "trips:nyc",
        "earliest": "2026-01",
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": "2026-01",
    }