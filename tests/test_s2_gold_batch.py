import pytest

from meridian.operational.control import record_job_attempt
from meridian.operational.gold_batch import run_gold_batch


GOOD = {"job": "trips:jc", "market": "jc", "month": "2021-02",}

def _record_silver(conn):
    record_job_attempt(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
        "SUCCESS",
    )
    conn.commit()


def test_gold_batch_runs_every_day(monkeypatch, conn):
    _record_silver(conn)
    calls = []

    def fake_gold_day(job, target_date):
        calls.append((job, target_date))

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_gold_day,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == [
        (GOOD["job"], f"{GOOD['month']}-{day:02d}")
        for day in range(1, 29)
    ]


def test_successful_days_are_recorded(conn, monkeypatch):
    _record_silver(conn)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: None,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM control_table
            WHERE job = 'station-daily'
              AND market = %s
              AND load_window LIKE %s
              AND status = 'SUCCESS'
            """,
            (
                GOOD["market"],
                f"{GOOD['month']}-%",
            ),
        )
        count = cur.fetchone()[0]

    assert count == 28


def test_failed_day_is_recorded_and_other_days_run(
    conn,
    monkeypatch,
):
    _record_silver(conn)
    calls = []

    def fake_gold_day(job, target_date):
        calls.append(target_date)

        if target_date == "2021-02-05":
            raise RuntimeError("gold failed")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_gold_day,
    )

    with pytest.raises(
        RuntimeError,
        match="2021-02-05",
    ):
        run_gold_batch(
            conn,
            GOOD["job"],
            GOOD["market"],
            GOOD["month"],
        )

    assert len(calls) == 28

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status
            FROM control_table
            WHERE job = 'station-daily'
              AND market = %s
              AND load_window = '2021-02-05'
            """,
            (GOOD["market"],),
        )
        status = cur.fetchone()[0]

    assert status == "FAILED"


def test_failed_days_are_reported_together(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    failed_days = {
        "2021-02-05",
        "2021-02-10",
    }

    def fake_gold_day(job, target_date):
        if target_date in failed_days:
            raise RuntimeError("gold failed")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_gold_day,
    )

    with pytest.raises(
        RuntimeError,
        match="2021-02-05.*2021-02-10",
    ):
        run_gold_batch(
            conn,
            GOOD["job"],
            GOOD["market"],
            GOOD["month"],
        )


def test_retry_runs_only_failed_days(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    failed_day = "2021-02-05"

    def first_run(job, target_date):
        if target_date == failed_day:
            raise RuntimeError("gold failed")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        first_run,
    )

    with pytest.raises(RuntimeError):
        run_gold_batch(
            conn,
            GOOD["job"],
            GOOD["market"],
            GOOD["month"],
        )

    calls = []

    def retry(job, target_date):
        calls.append(target_date)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        retry,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == [failed_day]


def test_completed_month_does_nothing(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: None,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    calls = []

    def unexpected_call(job, target_date):
        calls.append(target_date)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        unexpected_call,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == []


def test_successful_day_after_failed_attempt_is_not_retried(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    record_job_attempt(
        conn,
        "station-daily",
        GOOD["market"],
        "2021-02-05",
        "FAILED",
    )
    record_job_attempt(
        conn,
        "station-daily",
        GOOD["market"],
        "2021-02-05",
        "SUCCESS",
    )
    conn.commit()

    calls = []

    def fake_gold_day(job, target_date):
        calls.append(target_date)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_gold_day,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert "2021-02-05" not in calls
    assert len(calls) == 27


def test_gold_does_not_use_old_success_before_new_silver(
    conn,
    monkeypatch,
):
    record_job_attempt(
        conn,
        "station-daily",
        GOOD["market"],
        "2021-02-05",
        "SUCCESS",
    )
    conn.commit()

    _record_silver(conn)

    calls = []

    def fake_gold_day(job, target_date):
        calls.append(target_date)

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_gold_day,
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert "2021-02-05" in calls
    assert len(calls) == 28