import pytest

from meridian.operational.control import record_job_attempt
from meridian.operational.gold_batch import run_gold_batch


GOOD = {"job": "trips:jc", "market": "jc", "month": "2021-02",}


def _record_silver(conn) -> None:
    record_job_attempt(
        conn,
        "silver",
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
        "SUCCESS",
    )
    conn.commit()


def _record_gold(
    conn,
    target_date: str,
    status: str = "SUCCESS",
) -> None:
    record_job_attempt(
        conn,
        "gold",
        "station-daily",
        GOOD["market"],
        target_date,
        status,
    )
    conn.commit()


def test_gold_batch_runs_every_day(conn, monkeypatch):
    calls = []

    def fake_run(job, target_date):
        calls.append((job, target_date))

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_run,
    )
    _record_silver(conn)

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert len(calls) == 28
    assert calls[0] == (GOOD["job"], "2021-02-01")
    assert calls[-1] == (GOOD["job"], "2021-02-28")


def test_successful_days_are_recorded(conn, monkeypatch):
    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: None,
    )
    _record_silver(conn)

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
            WHERE layer = 'gold'
              AND job = 'station-daily'
              AND status = 'SUCCESS'
            """
        )
        count = cur.fetchone()[0]

    assert count == 28


def test_failed_day_is_recorded_and_other_days_run(
    conn,
    monkeypatch,
):
    calls = []

    def fake_run(job, target_date):
        calls.append(target_date)

        if target_date == "2021-02-03":
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_run,
    )
    _record_silver(conn)

    with pytest.raises(RuntimeError):
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
            WHERE layer = 'gold'
              AND load_window = '2021-02-03'
            """
        )
        status = cur.fetchone()[0]

    assert status == "FAILED"


def test_failed_days_are_reported_together(
    conn,
    monkeypatch,
):
    def fake_run(job, target_date):
        if target_date in {
            "2021-02-03",
            "2021-02-07",
        }:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        fake_run,
    )
    _record_silver(conn)

    with pytest.raises(RuntimeError) as error:
        run_gold_batch(
            conn,
            GOOD["job"],
            GOOD["market"],
            GOOD["month"],
        )

    message = str(error.value)

    assert "2021-02-03" in message
    assert "2021-02-07" in message


def test_retry_runs_only_failed_days(
    conn,
    monkeypatch,
):
    first_calls = []

    def first_run(job, target_date):
        first_calls.append(target_date)

        if target_date == "2021-02-03":
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        first_run,
    )
    _record_silver(conn)

    with pytest.raises(RuntimeError):
        run_gold_batch(
            conn,
            GOOD["job"],
            GOOD["market"],
            GOOD["month"],
        )

    retry_calls = []

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: retry_calls.append(target_date),
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert retry_calls == ["2021-02-03"]


def test_completed_month_does_no_gold_work(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    for day in range(1, 29):
        _record_gold(
            conn,
            f"2021-02-{day:02d}",
        )

    calls = []

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: calls.append(target_date),
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == []


def test_failed_then_successful_day_is_not_retried(
    conn,
    monkeypatch,
):
    _record_silver(conn)
    _record_gold(
        conn,
        "2021-02-03",
        "FAILED",
    )
    _record_gold(
        conn,
        "2021-02-03",
        "SUCCESS",
    )

    for day in range(1, 29):
        if day != 3:
            _record_gold(
                conn,
                f"2021-02-{day:02d}",
            )

    calls = []

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: calls.append(target_date),
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == []


def test_gold_before_latest_silver_is_rebuilt(
    conn,
    monkeypatch,
):
    _record_silver(conn)

    for day in range(1, 29):
        _record_gold(
            conn,
            f"2021-02-{day:02d}",
        )

    _record_silver(conn)

    calls = []

    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda job, target_date: calls.append(target_date),
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert len(calls) == 28