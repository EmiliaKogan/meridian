from calendar import monthrange

from meridian.operational.config import EARLIEST


def _silver_loaded_at(conn, job: str, market: str, month: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT loaded_at
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (job, market, month),
        )
        silver = cur.fetchone()

    return silver[0] if silver else None


def _days_in_month(month: str) -> int:
    year, month_number = map(int, month.split("-"))
    return monthrange(year, month_number)[1]


def _gold_days_complete(conn, market: str, month: str, silver_loaded_at,) -> bool:
    days = _days_in_month(month)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM operational_loads
            WHERE job = 'station-daily'
              AND market = %s
              AND load_window >= %s AND load_window <= %s
              AND loaded_at >= %s
            """,
            (
                market,
                f"{month}-01",
                f"{month}-{days:02d}",
                silver_loaded_at,
            ),
        )
        gold_count = cur.fetchone()[0]

    return gold_count == days


def _month_is_complete(conn, job: str, market: str, month: str) -> bool:
    silver_loaded_at = _silver_loaded_at(conn, job, market, month)

    if silver_loaded_at is None:
        return False

    return _gold_days_complete(conn, market, month, silver_loaded_at)


def _completed_months(conn, job: str, market: str, months: list[str], ) -> list[str]:
    """Return published months that are fully loaded."""
    return [
        month
        for month in months
        if _month_is_complete(conn, job, market, month)
    ]


def _published_months(conn, job: str, market: str) -> list[str]:
    """Return published Silver months for a job."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT load_window
            FROM operational_loads
            WHERE job = %s
              AND market = %s
            ORDER BY load_window
            """,
            (job, market),
        )
        return [row[0] for row in cur.fetchall()]


def _next_month(month: str) -> str:
    """Return the month after the given month."""
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


def _calculate_watermark(earliest: str, completed: set[str]) -> tuple[str | None, str]:
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
    """Return operational load progress for a job."""
    earliest = EARLIEST[job]
    market = job.split(":")[1]

    published = _published_months(conn, job, market)
    completed = set(_completed_months(conn, job, market, published))
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
        "gaps": _find_gaps(watermark, newest, completed, first_incomplete, ),
        "next": next_month,
    }

# def _month_is_complete(conn, job: str, market: str, month: str) -> bool:
#     """Return whether Silver and all Gold days are loaded for a month."""
#     with conn.cursor() as cur:
#         cur.execute(
#             """
#             SELECT loaded_at
#             FROM operational_loads
#             WHERE job = %s
#               AND market = %s
#               AND load_window = %s
#             """,
#             (job, market, month),
#         )
#         silver = cur.fetchone()

#     if silver is None:
#         return False

#     silver_loaded_at = silver[0]
#     year, month_number = map(int, month.split("-"))
#     days = monthrange(year, month_number)[1]

#     with conn.cursor() as cur:
#         cur.execute(
#             """
#             SELECT COUNT(*)
#             FROM operational_loads
#             WHERE job = 'station-daily'
#               AND market = %s
#               AND load_window >= %s
#               AND load_window <= %s
#               AND loaded_at >= %s
#             """,
#             (
#                 market,
#                 f"{month}-01",
#                 f"{month}-{days:02d}",
#                 silver_loaded_at,
#             ),
#         )
#         gold_count = cur.fetchone()[0]

#     return gold_count == days
# def progress(conn, job: str) -> dict:
#     """Return operational load progress for a job."""
#     earliest = EARLIEST[job]
#     market = job.split(":")[1]

#     if not _month_is_complete(conn, job, market, earliest):
#         return {
#             "job": job,
#             "earliest": earliest,
#             "watermark": None,
#             "complete": 0,
#             "gaps": [],
#             "next": earliest,
#         }

#     next_month = _next_month(earliest)

#     if _month_is_complete(conn, job, market, next_month):
#         return {
#             "job": job,
#             "earliest": earliest,
#             "watermark": next_month,
#             "complete": 2,
#             "gaps": [],
#             "next": _next_month(next_month),
#         }

#     return {
#         "job": job,
#         "earliest": earliest,
#         "watermark": earliest,
#         "complete": 1,
#         "gaps": [],
#         "next": next_month,
#     }