import subprocess

import pytest

from meridian.operational.job_runner import (
    _lock_window,
    call_bronze,
    call_silver,
    run_bronze,
    run_silver,
)


GOOD = ("trips:jc", "2026-06")


def _fake_subprocess(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(
        "meridian.operational.job_runner.subprocess.run",
        fake_run,
    )
    return calls


def _fake_runner(monkeypatch, name, error=None):
    calls = []

    def fake_run(job, month):
        calls.append((job, month))
        if error:
            raise error

    monkeypatch.setattr(
        f"meridian.operational.job_runner.{name}",
        fake_run,
    )
    return calls


def _fake_record(monkeypatch):
    calls = []

    def fake_record(*args):
        calls.append(args)

    monkeypatch.setattr(
        "meridian.operational.job_runner.record_job_attempt",
        fake_record,
    )
    return calls


class _ConnectionSpy:
    """Minimal connection spy for commit verification."""

    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_run_bronze_calls_stage1_in_process(monkeypatch):
    """Bronze calls the existing Stage 1 job in-process."""
    calls = []

    def fake_main():
        calls.append(list(__import__("sys").argv))

    monkeypatch.setattr(
        "meridian.operational.job_runner.bronze_main",
        fake_main,
    )

    run_bronze(*GOOD)

    assert calls == [
        ["ingest-to-bronze", "trips:jc", "2026-06"]
    ]


def test_run_silver_runs_stage1_container(monkeypatch):
    """Silver runs the existing Stage 1 job in the app container."""
    calls = _fake_subprocess(monkeypatch)

    run_silver(*GOOD)

    command, options = calls[0]
    assert command[-3:] == [
        "meridian.transform_to_silver.main",
        *GOOD,
    ]
    assert command[:8] == [
        "docker",
        "compose",
        "-p",
        "meridian",
        "run",
        "--rm",
        "--no-deps",
        "app",
    ]
    assert options["check"] is True


def test_call_bronze_records_success(monkeypatch, conn):
    """A successful Bronze attempt is recorded."""
    _fake_runner(monkeypatch, "run_bronze")
    records = _fake_record(monkeypatch)

    call_bronze(conn, *GOOD)

    assert records == [
        (conn, "bronze", "trips:jc", "jc", "2026-06", "SUCCESS")
    ]


def test_call_bronze_records_failure(monkeypatch, conn):
    """A failed Bronze attempt is recorded and propagated."""
    error = RuntimeError("boom")
    _fake_runner(monkeypatch, "run_bronze", error)
    records = _fake_record(monkeypatch)

    with pytest.raises(RuntimeError) as raised:
        call_bronze(conn, *GOOD)

    assert raised.value is error
    assert records == [
        (conn, "bronze", "trips:jc", "jc", "2026-06", "FAILED")
    ]

def test_call_silver_records_success(monkeypatch, conn):
    """A successful Silver attempt is recorded."""
    _fake_runner(monkeypatch, "run_silver")
    records = _fake_record(monkeypatch)

    call_silver(conn, *GOOD)

    assert records == [
        (conn, "silver", "trips:jc", "jc", "2026-06", "SUCCESS")
    ]


def test_call_silver_records_failure(monkeypatch, conn):
    """A failed Silver attempt is recorded and propagated."""
    error = subprocess.CalledProcessError(1, ["docker"])
    _fake_runner(monkeypatch, "run_silver", error)
    records = _fake_record(monkeypatch)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        call_silver(conn, *GOOD)

    assert raised.value is error
    assert records == [
        (conn, "silver", "trips:jc", "jc", "2026-06", "FAILED")
    ]


def test_lock_window_uses_postgres_advisory_lock(conn):
    """Silver window locking uses a PostgreSQL advisory transaction lock."""
    _lock_window(conn, *GOOD)

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

    assert count == 1