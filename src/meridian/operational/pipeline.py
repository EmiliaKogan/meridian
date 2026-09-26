from datetime import datetime, date, timedelta
import os
import psycopg
import subprocess
from calendar import monthrange

from meridian.operational.config import EARLIEST, JOBS
from meridian.operational.progress import progress

from meridian.ingest_to_bronze.ingest import download_source_zip, find_latest_csvs_in_zip, find_source_zip, save_bronze_csvs
from meridian.ingest_to_bronze.main import parse_dataset_market

from meridian.transform_to_gold.database import delete_day, insert_date, insert_events, insert_stations
from meridian.transform_to_gold.transform import build_date_row



def _validate_market(market: str) -> str:
    if market not in JOBS:
        raise ValueError(f"Unknown market: {market}")

    return JOBS[market]


def _validate_month(month: str) -> None:
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"Invalid month: {month}") from exc

    if parsed.strftime("%Y-%m") != month:
        raise ValueError(f"Invalid month: {month}")


def _validate_start_month(job: str, month: str) -> None:
    if month < EARLIEST[job]:
        raise ValueError(
            f"Month {month} is before earliest supported month "
            f"{EARLIEST[job]}"
        )


def _validate_range(start_month: str, end_month: str) -> None:
    if start_month > end_month:
        raise ValueError(
            f"Start month {start_month} is after end month {end_month}")



def _run_bronze(job: str, month: str) -> None:
    """Run the Stage 1 Bronze job."""
    _, market = parse_dataset_market(job)

    source_zip = find_source_zip(market, month)
    zip_path = download_source_zip(source_zip)

    try:
        csv_paths = find_latest_csvs_in_zip(zip_path,market,month,)
        save_bronze_csvs(zip_path,csv_paths,market,month,)
    finally:
        zip_path.unlink(missing_ok=True)


def _run_silver(job: str, month: str) -> None:
    """Run the Stage 1 Silver job."""
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


def _month_days(month: str) -> list[date]:
    """Return every date in a month."""
    year, month_number = map(int, month.split("-"))
    days = monthrange(year, month_number)[1]

    return [
        date(year, month_number, day)
        for day in range(1, days + 1)
    ]


def _run_gold_day(conn, target_date: date) -> None:
    """Run the Stage 1 Gold job for one day."""
    target_date_text = target_date.isoformat()

    delete_day(conn, target_date_text)
    insert_date(conn, build_date_row(target_date))
    insert_stations(conn, target_date_text)
    insert_events(conn, target_date_text)

    conn.commit()


def _run_gold(conn, month: str) -> None:
    """Run the Stage 1 Gold job for every day of the month."""
    for target_date in _month_days(month):
        _run_gold_day(conn, target_date)


def _next_month(month: str) -> str:
    """Return the month after the given month."""
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


def _resolve_start_month(conn, job: str, start_month: str | None,) -> str | None:
    if start_month is not None:
        return start_month

    return progress(conn, job)["next"]


def _run_month(conn, job: str, month: str) -> None:
    """Run all Stage 1 jobs for one month."""
    _run_bronze(job, month)
    _run_silver(job, month)
    _run_gold(conn, month)


def _run_month_range(conn, job: str, start_month: str, end_month: str,) -> None:
    """Run all months in the requested range."""
    month = start_month

    while month <= end_month:
        _run_month(conn, job, month)
        month = _next_month(month)


def run_pipeline(market: str, start_month: str | None = None, end_month: str | None = None,) -> None:
    """Validate and run the pipeline."""
    job = _validate_market(market)
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        start_month = _resolve_start_month(conn, job, start_month)

        if start_month is None:
            return

        _validate_month(start_month)
        _validate_start_month(job, start_month)

        if end_month is None:
            _run_month(conn, job, start_month)
            return

        _validate_month(end_month)
        _validate_range(start_month, end_month)
        _run_month_range(conn, job, start_month, end_month)


# def run_pipeline(market: str, start_month: str | None = None, end_month: str | None = None,) -> None:
#     """Validate and prepare a pipeline run."""
#     job = _validate_market(market)

#     database_url = os.environ["DATABASE_URL"]

#     with psycopg.connect(database_url) as conn:
#         if start_month is None:
#             next_month = progress(conn, job)["next"]

#             if next_month is None:
#                 return

#             start_month = next_month

#         _validate_month(end_month)
#         _validate_range(start_month, end_month)

#         month = start_month

#         while month <= end_month:
#             _run_bronze(job, month)
#             _run_silver(job, month)
#             _run_gold(month)
#             month = _next_month(month)


# def run_pipeline(market: str, start_month: str | None = None, end_month: str | None = None,) -> None:
#     """Validate and prepare a pipeline run."""
#     job = _validate_market(market)

#     if start_month is None:
#         next_month = progress(conn, job)["next"]

#         if next_month is None:
#             return

#         start_month = next_month

#     _validate_month(start_month)
#     _validate_start_month(job, start_month)

#     if end_month is None:
#         return

#     _validate_month(end_month)
#     _validate_range(start_month, end_month)