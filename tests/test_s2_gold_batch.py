import pytest
from datetime import date

from meridian.operational.control import record_job_attempt
from meridian.operational.gold_batch import (
    _prepare_silver_workspace,
    _run_gold_day,
    _lock_day,
    run_gold_batch,
)


GOOD = {
    "job": "trips:jc",
    "market": "jc",
    "month": "2021-02",
}


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

    monkeypatch.setattr(
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )

    def fake_run(conn, target_date):
        calls.append(target_date)

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
    assert calls[0] == "2021-02-01"
    assert calls[-1] == "2021-02-28"


def test_successful_days_are_recorded(conn, monkeypatch):
    monkeypatch.setattr(
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda conn, target_date: None,
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

    monkeypatch.setattr(
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )

    def fake_run(conn, target_date):
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
    monkeypatch.setattr(
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )

    def fake_run(conn, target_date):
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

    monkeypatch.setattr(
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )

    def first_run(conn, target_date):
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
        lambda conn, target_date: retry_calls.append(target_date),
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
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda conn, target_date: calls.append(target_date),
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
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda conn, target_date: calls.append(target_date),
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
        "meridian.operational.gold_batch._prepare_silver_workspace",
        lambda conn, market, month: None,
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch._run_gold_day",
        lambda conn, target_date: calls.append(target_date),
    )

    run_gold_batch(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    )

    assert len(calls) == 28


def test_run_gold_day_uses_existing_gold_functions(
    monkeypatch,
):
    calls = []
    conn = object()

    monkeypatch.setattr(
        "meridian.operational.gold_batch.delete_day",
        lambda db, day: calls.append(("delete", db, day)),
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch.build_date_row",
        lambda target: calls.append(("build", target)) or "row",
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch.insert_date",
        lambda db, row: calls.append(("date", db, row)),
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch.insert_stations",
        lambda db, day: calls.append(("stations", db, day)),
    )
    monkeypatch.setattr(
        "meridian.operational.gold_batch.insert_events",
        lambda db, day: calls.append(("events", db, day)),
    )

    _run_gold_day(conn, "2021-02-03")

    assert calls == [
        ("delete", conn, "2021-02-03"),
        ("build", date(2021, 2, 3)),
        ("date", conn, "row"),
        ("stations", conn, "2021-02-03"),
        ("events", conn, "2021-02-03"),
    ]


def test_prepare_silver_workspace_includes_all_markets_for_requested_month(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_rides (
                market,
                data_window,
                started_at,
                ended_at,
                start_station_id,
                end_station_id
            )
            VALUES
                (
                    'JC',
                    '2021-02',
                    '2021-02-03',
                    '2021-02-03',
                    'START-1',
                    'END-1'
                ),
                (
                    'JC',
                    '2021-03',
                    '2021-03-03',
                    '2021-03-03',
                    'START-2',
                    'END-2'
                ),
                (
                    'NYC',
                    '2021-02',
                    '2021-02-03',
                    '2021-02-03',
                    'START-3',
                    'END-3'
                )
            """
        )
    conn.commit()

    _prepare_silver_workspace(
        conn,
        GOOD["market"],
        GOOD["month"],
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT market, data_window
            FROM silver_rides
            """
        )
        rows = cur.fetchall()

    assert rows == [
    ("JC", "2021-02"),
    ("NYC", "2021-02"),
]


def test_lock_day_uses_only_date(conn):
    _lock_day(
        conn,
        "2021-02-03",
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM pg_locks
            WHERE locktype = 'advisory'
              AND pid = pg_backend_pid()
            """
        )
        count = cur.fetchone()[0]

    conn.rollback()

    assert count == 1
    

def test_gold_workspace_preserves_other_market_events(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_rides (
                market,
                data_window,
                started_at,
                ended_at,
                start_station_id,
                end_station_id
            )
            VALUES
                (
                    'JC',
                    '2021-02',
                    '2021-02-03 10:00:00+00',
                    '2021-02-03 10:15:00+00',
                    'JC-START',
                    'JC-END'
                ),
                (
                    'NYC',
                    '2021-02',
                    '2021-02-03 11:00:00+00',
                    '2021-02-03 11:15:00+00',
                    'NYC-START',
                    'NYC-END'
                )
            """
        )
    conn.commit()

    _prepare_silver_workspace(
        conn,
        "jc",
        "2021-02",
    )
    _run_gold_day(
        conn,
        "2021-02-03",
    )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT market, event_type, station_id
            FROM fact_events
            WHERE date_key = 20210203
              AND station_id IN (
                  'JC-START',
                  'JC-END',
                  'NYC-START',
                  'NYC-END'
              )
            ORDER BY market, event_type
            """
        )
        rows = cur.fetchall()

    assert rows == [
        ("JC", "arrival", "JC-END"),
        ("JC", "departure", "JC-START"),
        ("NYC", "arrival", "NYC-END"),
        ("NYC", "departure", "NYC-START"),
    ]


def test_gold_workspace_includes_arrival_from_previous_month(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_rides (
                market,
                data_window,
                started_at,
                ended_at,
                start_station_id,
                end_station_id
            )
            VALUES (
                'JC',
                '2021-01',
                '2021-01-31 23:55:00+00',
                '2021-02-01 00:10:00+00',
                'JC-START',
                'JC-END'
            )
            """
        )
    conn.commit()

    _prepare_silver_workspace(
        conn,
        "jc",
        "2021-02",
    )
    _run_gold_day(
        conn,
        "2021-02-01",
    )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_type, market, station_id
            FROM fact_events
            WHERE date_key = 20210201
            """
        )
        rows = cur.fetchall()

    assert rows == [
        ("arrival", "JC", "JC-END"),
    ]