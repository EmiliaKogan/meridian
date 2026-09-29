from calendar import monthrange

from meridian.operational.config import EARLIEST


def _silver_finished_at(conn, job: str, market: str, month: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT finished_at
            FROM control_table
            WHERE job = %s
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


def _days_in_month(month: str) -> int:
    year, month_number = map(int, month.split("-"))
    return monthrange(year, month_number)[1]


def _gold_day_count(
    conn,
    market: str,
    month: str,
    days: int,
    silver_finished_at,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT load_window)
            FROM control_table
            WHERE job = 'station-daily'
              AND market = %s
              AND load_window >= %s
              AND load_window <= %s
              AND status = 'SUCCESS'
              AND finished_at >= %s
            """,
            (
                market,
                f"{month}-01",
                f"{month}-{days:02d}",
                silver_finished_at,
            ),
        )
        return cur.fetchone()[0]


def _gold_days_complete(
    conn,
    market: str,
    month: str,
    silver_finished_at,
) -> bool:
    days = _days_in_month(month)

    gold_count = _gold_day_count(
        conn,
        market,
        month,
        days,
        silver_finished_at,
    )

    return gold_count == days


def _month_is_complete(conn, job: str, market: str, month: str,) -> bool:
    silver_finished_at = _silver_finished_at(conn, job, market, month,)

    if silver_finished_at is None:
        return False

    return _gold_days_complete(conn, market, month,silver_finished_at,)


def _completed_months(conn, job: str, market: str, months: list[str],) -> list[str]:
    return [
        month
        for month in months
        if _month_is_complete(conn, job, market, month)
    ]


def _published_months(conn, job: str, market: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT load_window
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND status = 'SUCCESS'
            ORDER BY load_window
            """,
            (job, market),
        )
        return [row[0] for row in cur.fetchall()]


def _next_month(month: str) -> str:
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


def _calculate_watermark(earliest: str, completed: set[str],) -> tuple[str | None, str]:
    watermark = None
    month = earliest

    while month in completed:
        watermark = month
        month = _next_month(month)

    return watermark, month


def _find_gaps(watermark: str | None, newest: str | None, completed: set[str], first_incomplete: str,) -> list[str]:
    if watermark is None or newest is None or first_incomplete > newest:
        return []

    gaps = []
    month = first_incomplete

    while month <= newest:
        if month not in completed:
            gaps.append(month)

        month = _next_month(month)

    return gaps


def progress(conn, job: str) -> dict:
    earliest = EARLIEST[job]
    market = job.split(":")[1]

    published = _published_months(conn, job, market)
    completed = set(_completed_months(conn, job, market, published,))

    watermark, first_incomplete = _calculate_watermark(earliest, completed,)

    newest = published[-1] if published else None

    if newest is None:
        next_month = earliest
    elif first_incomplete <= newest:
        next_month = first_incomplete
    else:
        next_month = None

    return {
        "job": job,
        "earliest": earliest,
        "watermark": watermark,
        "complete": len(completed),
        "gaps": _find_gaps(watermark, newest, completed, first_incomplete,),
        "next": next_month,
    }