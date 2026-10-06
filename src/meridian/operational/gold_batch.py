from calendar import monthrange
from datetime import date

from meridian.operational.control import record_job_attempt
from meridian.transform_to_gold.database import (
    delete_day,
    insert_date,
    insert_events,
    insert_stations,
)
from meridian.transform_to_gold.transform import build_date_row


def _run_gold_day(conn, target_date: str) -> None:
    target = date.fromisoformat(target_date)
    delete_day(conn, target_date)
    date_row = build_date_row(target)
    insert_date(conn, date_row)
    insert_stations(conn, target_date)
    insert_events(conn, target_date)


def _prepare_silver_workspace(conn, market: str, month: str) -> None:
    month_start = f"{month}-01"

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS pg_temp.silver_rides")
        cur.execute(
            """
            CREATE TEMP TABLE silver_rides AS
            SELECT *
            FROM public.silver_rides
            WHERE (
                started_at >= %s::date
                AND started_at < (%s::date + INTERVAL '1 month')
            )
            OR (
                ended_at >= %s::date
                AND ended_at < (%s::date + INTERVAL '1 month')
            )
            """,
            (month_start, month_start, month_start, month_start),
        )


def _lock_day(
    conn,
    target_date: str,
) -> None:
    date_key = int(target_date.replace("-", ""))

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (date_key,),
        )


def _silver_finished_at(
    conn,
    job: str,
    market: str,
    month: str,
):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT finished_at
            FROM control_table
            WHERE layer = 'silver'
              AND job = %s
              AND market = %s
              AND load_window = %s
              AND status = 'SUCCESS'
            ORDER BY finished_at DESC
            LIMIT 1
            """,
            (job, market, month),
        )
        row = cur.fetchone()

    return row[0] if row else None


def _successful_days(
    conn,
    market: str,
    month: str,
    silver_finished_at,
) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT load_window
            FROM control_table
            WHERE layer = 'gold'
              AND job = 'station-daily'
              AND market = %s
              AND load_window LIKE %s
              AND status = 'SUCCESS'
              AND finished_at >= %s
            """,
            (market, f"{month}-%", silver_finished_at),
        )
        return {row[0] for row in cur.fetchall()}


def _days_in_month(month: str) -> int:
    year, month_number = map(int, month.split("-"))
    return monthrange(year, month_number)[1]


def _record(
    conn,
    market: str,
    target_date: str,
    status: str,
) -> None:
    record_job_attempt(
        conn,
        "gold",
        "station-daily",
        market,
        target_date,
        status,
    )
    conn.commit()


def _require_silver(
    conn,
    job: str,
    market: str,
    month: str,
):
    finished_at = _silver_finished_at(
        conn,
        job,
        market,
        month,
    )

    if finished_at is None:
        raise ValueError(
            f"No successful Silver load for {job} {month}"
        )

    return finished_at


def _run_missing_days(
    conn,
    market: str,
    month: str,
    successful: set[str],
) -> list[str]:
    failed = []

    for day in range(1, _days_in_month(month) + 1):
        target_date = f"{month}-{day:02d}"

        if target_date in successful:
            continue

        try:
            _lock_day(conn, target_date)
            _run_gold_day(conn, target_date)
            _record(conn, market, target_date, "SUCCESS")
        except Exception:
            conn.rollback()
            _record(conn, market, target_date, "FAILED")
            failed.append(target_date)

    return failed


def _raise_for_failed_days(failed: list[str]) -> None:
    if failed:
        raise RuntimeError(
            f"Gold failed for days: {', '.join(failed)}"
        )


def run_gold_batch(conn, job: str, market: str, month: str,) -> None:
    silver_finished_at = _require_silver(conn, job, market, month,)
    successful = _successful_days(conn, market, month, silver_finished_at,)

    if len(successful) == _days_in_month(month):
        return

    _prepare_silver_workspace(conn, market, month,)

    failed = _run_missing_days(conn, market, month, successful,)
    _raise_for_failed_days(failed)