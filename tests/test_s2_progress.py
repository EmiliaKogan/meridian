from meridian.operational.control import record_job_attempt
from meridian.operational.progress import progress, month_is_complete


GOOD = {"job": "trips:jc", "market": "jc", "month": "2021-01",}


def _record(
    conn,
    layer: str,
    job: str,
    window: str,
    status: str = "SUCCESS",
) -> None:
    record_job_attempt(
        conn,
        layer,
        job,
        GOOD["market"],
        window,
        status,
    )
    conn.commit()


def _record_bronze(conn, month: str) -> None:
    _record(
        conn,
        "bronze",
        GOOD["job"],
        month,
    )


def _record_silver(conn, month: str) -> None:
    _record(
        conn,
        "silver",
        GOOD["job"],
        month,
    )


def _record_gold_month(
    conn,
    month: str,
    days: int,
) -> None:
    for day in range(1, days + 1):
        _record(
            conn,
            "gold",
            "station-daily",
            f"{month}-{day:02d}",
        )


def _complete_month(
    conn,
    month: str,
    days: int,
) -> None:
    _record_bronze(conn, month)
    _record_silver(conn, month)
    _record_gold_month(conn, month, days)


def test_no_loads_has_no_complete_months(conn):
    result = progress(conn, GOOD["job"])

    assert result == {
        "job": GOOD["job"],
        "earliest": "2021-01",
        "watermark": None,
        "complete": 0,
        "gaps": [],
        "next": "2021-01",
    }


def test_bronze_only_is_not_complete(conn):
    _record_bronze(conn, GOOD["month"])

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0
    assert result["watermark"] is None
    assert result["next"] == GOOD["month"]


def test_silver_without_bronze_is_not_complete(conn):
    _record_silver(conn, GOOD["month"])
    _record_gold_month(conn, GOOD["month"], 31)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_bronze_and_silver_without_gold_are_not_complete(conn):
    _record_bronze(conn, GOOD["month"])
    _record_silver(conn, GOOD["month"])

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_missing_gold_day_makes_month_incomplete(conn):
    _record_bronze(conn, GOOD["month"])
    _record_silver(conn, GOOD["month"])
    _record_gold_month(conn, GOOD["month"], 30)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_complete_month_is_counted(conn):
    _complete_month(conn, GOOD["month"], 31)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 1
    assert result["watermark"] == GOOD["month"]


def test_two_consecutive_complete_months_advance_watermark(conn):
    _complete_month(conn, "2021-01", 31)
    _complete_month(conn, "2021-02", 28)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 2
    assert result["watermark"] == "2021-02"


def test_gap_is_reported(conn):
    _complete_month(conn, "2021-01", 31)
    _complete_month(conn, "2021-02", 28)
    _complete_month(conn, "2021-04", 30)

    result = progress(conn, GOOD["job"])

    assert result["watermark"] == "2021-02"
    assert result["complete"] == 3
    assert result["gaps"] == ["2021-03"]
    assert result["next"] == "2021-03"


def test_later_complete_month_does_not_skip_earliest(conn):
    _complete_month(conn, "2021-02", 28)

    result = progress(conn, GOOD["job"])

    assert result["watermark"] is None
    assert result["complete"] == 1
    assert result["next"] == "2021-01"


def test_failed_bronze_does_not_count(conn):
    _record(
        conn,
        "bronze",
        GOOD["job"],
        GOOD["month"],
        "FAILED",
    )
    _record_silver(conn, GOOD["month"])
    _record_gold_month(conn, GOOD["month"], 31)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_failed_silver_does_not_count(conn):
    _record_bronze(conn, GOOD["month"])
    _record(
        conn,
        "silver",
        GOOD["job"],
        GOOD["month"],
        "FAILED",
    )
    _record_gold_month(conn, GOOD["month"], 31)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_failed_gold_day_does_not_count(conn):
    _record_bronze(conn, GOOD["month"])
    _record_silver(conn, GOOD["month"])
    _record_gold_month(conn, GOOD["month"], 30)
    _record(
        conn,
        "gold",
        "station-daily",
        "2021-01-31",
        "FAILED",
    )

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0


def test_silver_before_latest_bronze_is_stale(conn):
    _complete_month(conn, GOOD["month"], 31)
    _record_bronze(conn, GOOD["month"])

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0
    assert result["next"] == GOOD["month"]


def test_gold_before_latest_silver_is_stale(conn):
    _complete_month(conn, GOOD["month"], 31)
    _record_silver(conn, GOOD["month"])

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 0
    assert result["next"] == GOOD["month"]


def test_success_after_failed_attempt_counts(conn):
    _record(
        conn,
        "bronze",
        GOOD["job"],
        GOOD["month"],
        "FAILED",
    )
    _complete_month(conn, GOOD["month"], 31)

    result = progress(conn, GOOD["job"])

    assert result["complete"] == 1


def test_nyc_uses_its_configured_earliest(conn):
    result = progress(conn, "trips:nyc")

    assert result["earliest"] == "2026-01"
    assert result["next"] == "2026-01"


def test_month_is_complete_for_complete_month(conn):
    _complete_month(conn, GOOD["month"], 31)

    assert month_is_complete(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    ) is True


def test_month_is_not_complete_without_loads(conn):
    assert month_is_complete(
        conn,
        GOOD["job"],
        GOOD["market"],
        GOOD["month"],
    ) is False