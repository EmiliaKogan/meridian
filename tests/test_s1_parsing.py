import pytest

from meridian.parsing import parse_dataset_market, parse_month


GOOD = {
    "job": "trips:jc",
    "market": "JC",
    "month": "2026-06",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("trips:jc", ("trips", "JC")),
        ("trips:JC", ("trips", "JC")),
        ("trips:nyc", ("trips", "NYC")),
        ("trips:NYC", ("trips", "NYC")),
    ],
)
def test_parse_dataset_market_accepts_supported_jobs(value, expected):
    assert parse_dataset_market(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("stations:jc", "Unknown dataset"),
        ("trips:la", "Unknown market"),
        ("trips:", "Unknown market"),
    ],
)
def test_parse_dataset_market_rejects_unknown_values(value, message):
    with pytest.raises(ValueError, match=message):
        parse_dataset_market(value)


def test_parse_dataset_market_rejects_missing_separator():
    with pytest.raises(ValueError):
        parse_dataset_market("trips")


@pytest.mark.parametrize("value", ["2026-06", "2024-02", "0001-01", "2026-12"])
def test_parse_month_accepts_canonical_months(value):
    assert parse_month(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-15",  # A day is not a monthly window.
        "2026-6",     # Require YYYY-MM, not YYYY-M.
        "2026-00",
        "2026-13",
        "0000-01",
        "2026/06",
        "202606",
        "not-a-month",
        "",
    ],
)
def test_parse_month_rejects_invalid_months(value):
    with pytest.raises(ValueError, match="Invalid month"):
        parse_month(value)


def test_parse_month_does_not_silently_change_the_window():
    assert parse_month(GOOD["month"]) == GOOD["month"]


def test_bronze_silver_inspect_use_shared_job_parser():
    from meridian.ingest_to_bronze.main import parse_dataset_market as bronze_parser
    from meridian.inspect.main import parse_dataset_market as inspect_parser
    from meridian.transform_to_silver.main import parse_dataset_market as silver_parser

    assert bronze_parser is parse_dataset_market
    assert silver_parser is parse_dataset_market
    assert inspect_parser is parse_dataset_market