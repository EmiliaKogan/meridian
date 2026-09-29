import subprocess
from calendar import monthrange

from meridian.operational.control import record_job_attempt


def _run_gold_day(job: str, target_date: str) -> None:
    subprocess.run(
        [
            "just",
            "run",
            "transform-to-gold",
            "station-daily",
            target_date,
        ],
        check=True,
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
    job: str,
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
            _run_gold_day(job, target_date)
            _record(conn, market, target_date, "SUCCESS")
        except Exception:
            _record(conn, market, target_date, "FAILED")
            failed.append(target_date)

    return failed


def _raise_for_failed_days(failed: list[str]) -> None:
    if failed:
        raise RuntimeError(
            f"Gold failed for days: {', '.join(failed)}"
        )


def run_gold_batch(
    conn,
    job: str,
    market: str,
    month: str,
) -> None:
    silver_finished_at = _require_silver(
        conn,
        job,
        market,
        month,
    )
    successful = _successful_days(
        conn,
        market,
        month,
        silver_finished_at,
    )
    failed = _run_missing_days(
        conn,
        job,
        market,
        month,
        successful,
    )
    _raise_for_failed_days(failed)