import argparse
import os
import time
import urllib.parse

import psycopg

from meridian.operational.client import dag_id, request, token
from meridian.operational.config import EARLIEST
from meridian.operational.progress import month_is_complete, progress
from meridian.operational.publication import is_published


POLL_SECONDS = 3
BACKFILL_MAX_ACTIVE_RUNS = 3


def _job_for_market(market: str) -> str:
    job = f"trips:{market}"
    if job not in EARLIEST:
        raise ValueError(f"Unknown market: {market}")
    return job


def _validate_month(job: str, month: str) -> None:
    try:
        year, number = map(int, month.split("-"))
        valid = len(month) == 7 and month[4] == "-"
        valid &= year >= 1 and 1 <= number <= 12
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"Invalid month: {month}")


def _validate_range(job: str, start: str, end: str) -> None:
    _validate_month(job, start)
    _validate_month(job, end)
    if start > end:
        raise ValueError("Start month cannot be after end month")


def _trigger_month(market: str, month: str, api_token: str) -> dict:
    return request(
        "POST",
        f"/api/v2/dags/{dag_id(market)}/dagRuns",
        {"logical_date": None, "conf": {"month": month}},
        api_token,
    )


def _run_path(market: str, run_id: str) -> str:
    run_id = urllib.parse.quote(run_id, safe="")
    return f"/api/v2/dags/{dag_id(market)}/dagRuns/{run_id}"


def _wait_for_run(market: str, run_id: str, api_token: str) -> dict:
    path = _run_path(market, run_id)
    while True:
        run = request("GET", path, token=api_token)
        if run["state"] in ("success", "failed"):
            return run
        time.sleep(POLL_SECONDS)


def _run_named_month(market: str, month: str) -> None:
    api_token = token()
    run = _trigger_month(market, month, api_token)
    finished = _wait_for_run(market, run["dag_run_id"], api_token)
    if finished["state"] != "success":
        raise RuntimeError(f"Airflow run failed for {market} {month}")


def _create_backfill(
    market: str,
    start: str,
    end: str,
    api_token: str,
) -> dict:
    body = {
        "dag_id": dag_id(market),
        "from_date": f"{start}-01T00:00:00Z",
        "to_date": f"{end}-01T00:00:00Z",
        "run_backwards": False,
        "dag_run_conf": {},
        "reprocess_behavior": "completed",
        "max_active_runs": BACKFILL_MAX_ACTIVE_RUNS,
    }
    return request("POST", "/api/v2/backfills", body, api_token)


def _wait_for_backfill(backfill_id: int, api_token: str) -> None:
    path = f"/api/v2/backfills/{backfill_id}"
    while True:
        backfill = request("GET", path, token=api_token)
        if backfill["completed_at"] is not None:
            return
        time.sleep(POLL_SECONDS)


def _next_month(month: str) -> str:
    year, number = map(int, month.split("-"))
    if number == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{number + 1:02d}"


def _months_in_range(start: str, end: str) -> list[str]:
    months = []
    while start <= end:
        months.append(start)
        start = _next_month(start)
    return months


def _incomplete_months(
    job: str,
    market: str,
    start: str,
    end: str,
) -> list[str]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return [
            month
            for month in _months_in_range(start, end)
            if not month_is_complete(conn, job, market, month)
        ]


def _run_backfill(market: str, start: str, end: str) -> None:
    api_token = token()
    backfill = _create_backfill(market, start, end, api_token)
    _wait_for_backfill(backfill["id"], api_token)
    failed = _incomplete_months(
        _job_for_market(market), market, start, end
    )
    if failed:
        raise RuntimeError(
            f"Backfill failed for months: {', '.join(failed)}"
        )


def _next_due_month(job: str) -> str | None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return progress(conn, job)["next"]


def run_pipeline(
    market: str,
    start_month: str | None = None,
    end_month: str | None = None,
) -> None:
    job = _job_for_market(market)
    if end_month is not None:
        _validate_range(job, start_month, end_month)
        _run_backfill(market, start_month, end_month)
        return
    if start_month is not None:
        _validate_month(job, start_month)
        _run_named_month(market, start_month)
        return
    month = _next_due_month(job)
    if month is not None and is_published(market, month):
        _run_named_month(market, month)


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("market")
    parser.add_argument("start_month", nargs="?")
    parser.add_argument("end_month", nargs="?")
    return parser.parse_args(args)


def run_cli() -> None:
    args = parse_args()
    run_pipeline(args.market, args.start_month, args.end_month)


if __name__ == "__main__":
    run_cli()