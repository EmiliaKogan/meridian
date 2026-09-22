from calendar import monthrange
from datetime import date


EARLIEST = {
    "trips:jc": "2021-01",
    "trips:nyc": "2026-01",
}


def _month_is_complete(conn, job: str, market: str, month: str) -> bool:
    """Return whether Silver and all Gold days are loaded for a month."""
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

    if silver is None:
        return False

    silver_loaded_at = silver[0]
    year, month_number = map(int, month.split("-"))
    days = monthrange(year, month_number)[1]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM operational_loads
            WHERE job = 'station-daily'
              AND market = %s
              AND load_window >= %s
              AND load_window <= %s
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


def _next_month(month: str) -> str:
    """Return the month after the given month."""
    year, month_number = map(int, month.split("-"))

    if month_number == 12:
        return f"{year + 1}-01"

    return f"{year}-{month_number + 1:02d}"


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


def _complete_months(conn, job: str, market: str, months: list[str],) -> list[str]:
    """Return published months that are fully loaded."""
    return [
        month
        for month in months
        if _month_is_complete(conn, job, market, month)
    ]


def progress(conn, job: str) -> dict:
    """Return operational load progress for a job."""
    earliest = EARLIEST[job]
    market = job.split(":")[1]

    published = _published_months(conn, job, market)
    complete_months = _complete_months(conn, job, market, published)

    complete_set = set(complete_months)
    month = earliest
    watermark = None

    while month in complete_set:
        watermark = month
        month = _next_month(month)

    complete = len(complete_months)

    newest = published[-1] if published else None
    gaps = []

    if watermark and newest and month <= newest:
        gap = month

        while gap <= newest:
            if gap not in complete_set:
                gaps.append(gap)

            gap = _next_month(gap)

    if not published:
        next_month = earliest
    elif month <= newest:
        next_month = month
    else:
        next_month = None

    return {
        "job": job,
        "earliest": earliest,
        "watermark": watermark,
        "complete": complete,
        "gaps": gaps,
        "next": next_month,
    }

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