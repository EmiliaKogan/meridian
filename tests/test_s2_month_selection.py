import pytest
from calendar import monthrange
from meridian.operational.control import record_load
from meridian.operational.month_selection import select_month


GOOD = {"job": "trips:jc", "market": "jc", "window": "2021-01",}


def record_complete_month(conn, job: str, market: str, month: str) -> None:
    """Record Silver and all Gold loads for a complete month."""
    record_load(conn, job, market, month)

    year, month_number = map(int, month.split("-"))
    days = monthrange(year, month_number)[1]

    for day in range(1, days + 1):
        record_load(conn, "station-daily", market,f"{month}-{day:02d}",)


def test_selects_earliest_month_when_nothing_is_loaded(conn):
    result = select_month(conn, GOOD["job"])

    assert result == "2021-01"

# silver is loaded but gold is not -> month incomplete -> the same month need to be completed
def test_selects_earliest_incomplete_month(conn): 
    record_load(conn, GOOD["job"], GOOD["market"], "2021-01")

    result = select_month(conn, GOOD["job"])

    assert result == "2021-01"


def test_selects_gap_before_later_complete_month(conn):
    record_complete_month(conn, GOOD["job"], GOOD["market"], "2021-01",)
    record_complete_month(conn, GOOD["job"], GOOD["market"], "2021-02",)
    record_complete_month(conn, GOOD["job"], GOOD["market"], "2021-04",)

    result = select_month(conn, GOOD["job"])

    assert result == "2021-03"


def test_returns_none_when_nothing_is_due(conn):
    record_complete_month(conn, GOOD["job"], GOOD["market"], "2021-01",)

    result = select_month(conn, GOOD["job"])

    assert result is None


def test_selects_earliest_month_when_first_month_is_incomplete(conn):
    record_load(conn, GOOD["job"], GOOD["market"], "2021-01")
    record_complete_month(conn, GOOD["job"], GOOD["market"], "2021-02",)

    result = select_month(conn, GOOD["job"])

    assert result == "2021-01"


def test_selects_nyc_earliest_month(conn):
    result = select_month(conn, "trips:nyc")

    assert result == "2026-01"

# def test_returns_requested_month(conn):
#     result = select_month(conn, GOOD["job"], requested_month="2021-05", )

#     assert result == "2021-05"


# # if requested run for a month already complete -> does nothing: success, work skipped.
# def test_returns_none_when_requested_month_is_complete(conn):
#     record_complete_month(conn,GOOD["job"], GOOD["market"], "2021-01", )

#     result = select_month(conn, GOOD["job"], requested_month="2021-01", )

#     assert result is None


# def test_rejects_month_before_earliest(conn):
#     with pytest.raises(ValueError):
#         select_month(conn, GOOD["job"], requested_month="2020-12", )


# def test_returns_requested_unpublished_month(conn):
#     result = select_month(conn, GOOD["job"], requested_month="2021-05", )

#     assert result == "2021-05"