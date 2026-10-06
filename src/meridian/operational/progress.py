from calendar import monthrange

from meridian.operational.config import EARLIEST


def _latest_success(
    conn,
    layer: str,
    job: str,
    market: str,
    window: str,
    after=None,
):
    query = """
        SELECT finished_at
        FROM control_table
        WHERE layer = %s
          AND job = %s
          AND market = %s
          AND load_window = %s
          AND status = 'SUCCESS'
    """
    params = [layer, job, market, window]

    if after is not None:
        query += " AND finished_at >= %s"
        params.append(after)

    query += " ORDER BY finished_at DESC LIMIT 1"

    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()

    return row[0] if row else None


def _days_in_month(month: str) -> int:
    year, month_number = map(int, month.split("-"))
    return monthrange(year, month_number)[1]


def _month_bounds(month: str) -> tuple[str, str]:
    days = _days_in_month(month)
    return f"{month}-01", f"{month}-{days:02d}"


def _gold_day_count(
    conn,
    market: str,
    month: str,
    silver_finished_at,
) -> int:
    first_day, last_day = _month_bounds(month)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT load_window)
            FROM control_table
            WHERE layer = 'gold'
              AND job = 'station-daily'
              AND market = %s
              AND load_window BETWEEN %s AND %s
              AND status = 'SUCCESS'
              AND finished_at >= %s
            """,
            (market, first_day, last_day, silver_finished_at),
        )
        return cur.fetchone()[0]


def month_is_complete(
    conn,
    job: str,
    market: str,
    month: str,
) -> bool:
    bronze = _latest_success(
        conn, "bronze", job, market, month
    )

    if bronze is None:
        return False

    silver = _latest_success(
        conn, "silver", job, market, month, bronze
    )

    if silver is None:
        return False

    return _gold_day_count(
        conn,
        market,
        month,
        silver,
    ) == _days_in_month(month)


def _candidate_months(
    conn,
    job: str,
    market: str,
) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT load_window
            FROM control_table
            WHERE job = %s
              AND market = %s
              AND layer IN ('bronze', 'silver')
            ORDER BY load_window
            """,
            (job, market),
        )
        return [row[0] for row in cur.fetchall()]


def _completed_months(
    conn,
    job: str,
    market: str,
    months: list[str],
) -> list[str]:
    return [
        month
        for month in months
        if month_is_complete(conn, job, market, month)
    ]


def _next_month(month: str) -> str:
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


def _calculate_watermark(
    earliest: str,
    completed: set[str],
) -> tuple[str | None, str]:
    watermark = None
    month = earliest

    while month in completed:
        watermark = month
        month = _next_month(month)

    return watermark, month


def _find_gaps(
    watermark: str | None,
    newest_complete: str | None,
    completed: set[str],
    first_incomplete: str,
) -> list[str]:
    if watermark is None or newest_complete is None:
        return []

    gaps = []
    month = first_incomplete

    while month < newest_complete:
        if month not in completed:
            gaps.append(month)

        month = _next_month(month)

    return gaps


def progress(conn, job: str) -> dict:
    earliest = EARLIEST[job]
    market = job.split(":")[1]
    candidates = _candidate_months(conn, job, market)
    completed = set(_completed_months(conn, job, market, candidates,))
    watermark, first_incomplete = _calculate_watermark( earliest, completed,)
    newest_complete = max(completed) if completed else None

    return {
        "job": job,
        "earliest": earliest,
        "watermark": watermark,
        "complete": len(completed),
        "gaps": _find_gaps(watermark, newest_complete, completed, first_incomplete,),
        "next": first_incomplete,
    }