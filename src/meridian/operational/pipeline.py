import os
import subprocess
from calendar import monthrange

import psycopg

from meridian.operational.config import EARLIEST
from meridian.operational.progress import progress


def _run_bronze(job: str, month: str) -> None:
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            job,
            month,
        ],
        check=True,
    )


def _run_silver(job: str, month: str) -> None:
    subprocess.run(
        [
            "just",
            "run",
            "transform-to-silver",
            job,
            month,
        ],
        check=True,
    )


def _run_gold(job: str, month: str) -> None:
    days = monthrange(
        int(month[:4]),
        int(month[5:]),
    )[1]

    for day in range(1, days + 1):
        subprocess.run(
            [
                "just",
                "run",
                "transform-to-gold",
                "station-daily",
                f"{month}-{day:02d}",
            ],
            check=True,
        )


def _job_for_market(market: str) -> str:
    job = f"trips:{market}"

    if job not in EARLIEST:
        raise ValueError(f"Unknown market: {market}")

    return job


def _validate_month(job: str, month: str) -> None:
    try:
        year, month_number = map(int, month.split("-"))
        if len(month) != 7 or month[4] != "-":
            raise ValueError
        if year < 1 or not 1 <= month_number <= 12:
            raise ValueError
    except ValueError:
        raise ValueError(f"Invalid month: {month}")

    if month < EARLIEST[job]:
        raise ValueError(
            f"Month {month} is before earliest {EARLIEST[job]}"
        )


def _next_month(month: str) -> str:
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


def _months_in_range(
    start_month: str,
    end_month: str,
) -> list[str]:
    months = []
    month = start_month

    while month <= end_month:
        months.append(month)
        month = _next_month(month)

    return months


def _run_month(job: str, month: str) -> None:
    _run_bronze(job, month)
    _run_silver(job, month)
    _run_gold(job, month)


def run_pipeline(market: str, start_month: str | None = None, end_month: str | None = None,) -> None:
    job = _job_for_market(market)

    if start_month is None:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            start_month = progress(conn, job)["next"]

        if start_month is None:
            return

    _validate_month(job, start_month)

    if end_month is None:
        _run_month(job, start_month)
        return

    _validate_month(job, end_month)

    if start_month > end_month:
        raise ValueError(
            "Start month cannot be after end month"
        )

    for month in _months_in_range(
        start_month,
        end_month,
    ):
        _run_month(job, month)