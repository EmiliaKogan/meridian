import pytest

from meridian.operational.pipeline import (
    _create_backfill,
    _months_in_range,
    _wait_for_backfill,
    parse_args,
    run_cli,
    run_pipeline,
)


GOOD = {
    "job": "trips:jc",
    "market": "jc",
    "month": "2021-02",
}


def _fake_named_run(monkeypatch):
    calls = []

    def fake_run(market, month):
        calls.append((market, month))

    monkeypatch.setattr(
        "meridian.operational.pipeline._run_named_month",
        fake_run,
    )
    return calls


def test_pipeline_runs_named_month(monkeypatch):
    """A named month is delegated to Airflow."""
    calls = _fake_named_run(monkeypatch)

    run_pipeline(
        GOOD["market"],
        GOOD["month"],
    )

    assert calls == [
        (GOOD["market"], GOOD["month"])
    ]


def test_pipeline_runs_next_due_month(monkeypatch):
    """A windowless run delegates the next published month."""
    calls = _fake_named_run(monkeypatch)
    monkeypatch.setattr(
        "meridian.operational.pipeline._next_due_month",
        lambda job: GOOD["month"],
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.is_published",
        lambda market, month: True,
    )

    run_pipeline(GOOD["market"])

    assert calls == [
        (GOOD["market"], GOOD["month"])
    ]


def test_pipeline_does_nothing_when_no_month_is_due(
    monkeypatch,
):
    """A windowless run does nothing when no month is due."""
    calls = _fake_named_run(monkeypatch)
    monkeypatch.setattr(
        "meridian.operational.pipeline._next_due_month",
        lambda job: None,
    )

    run_pipeline(GOOD["market"])

    assert calls == []


def test_pipeline_does_nothing_when_month_is_unpublished(
    monkeypatch,
):
    """A windowless run does nothing for an unpublished month."""
    calls = _fake_named_run(monkeypatch)
    monkeypatch.setattr(
        "meridian.operational.pipeline._next_due_month",
        lambda job: GOOD["month"],
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.is_published",
        lambda market, month: False,
    )

    run_pipeline(GOOD["market"])

    assert calls == []


def test_pipeline_delegates_month_before_earliest(monkeypatch):
    """A month before earliest is delegated to Airflow."""
    calls = _fake_named_run(monkeypatch)

    run_pipeline(
        GOOD["market"],
        "2020-12",
    )

    assert calls == [
        (GOOD["market"], "2020-12")
    ]


def test_pipeline_rejects_invalid_month(monkeypatch):
    """An invalid month is rejected."""
    calls = _fake_named_run(monkeypatch)

    with pytest.raises(ValueError):
        run_pipeline(
            GOOD["market"],
            "2021-13",
        )

    assert calls == []


def test_pipeline_rejects_invalid_market(monkeypatch):
    """An unknown market is rejected."""
    calls = _fake_named_run(monkeypatch)

    with pytest.raises(ValueError):
        run_pipeline(
            "bad",
            GOOD["month"],
        )

    assert calls == []


def test_pipeline_runs_range_as_backfill(monkeypatch):
    """A named range is delegated to one Airflow backfill."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.pipeline._run_backfill",
        lambda *args: calls.append(args),
    )

    run_pipeline(
        "jc",
        "2021-01",
        "2021-02",
    )

    assert calls == [
        ("jc", "2021-01", "2021-02")
    ]


def test_pipeline_rejects_reversed_range(monkeypatch):
    """A range cannot end before it starts."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.pipeline._run_backfill",
        lambda *args: calls.append(args),
    )

    with pytest.raises(ValueError):
        run_pipeline(
            "jc",
            "2021-02",
            "2021-01",
        )

    assert calls == []


def test_create_backfill_uses_airflow_api(monkeypatch):
    """A range creates one real Airflow backfill."""
    calls = []

    def fake_request(method, path, body=None, token=None):
        calls.append((method, path, body, token))
        return {"id": 7}

    monkeypatch.setattr(
        "meridian.operational.pipeline.request",
        fake_request,
    )

    result = _create_backfill(
        "jc",
        "2021-01",
        "2021-02",
        "TOKEN",
    )

    assert result == {"id": 7}
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/v2/backfills"
    assert calls[0][2] == {
        "dag_id": "meridian_jc_monthly",
        "from_date": "2021-01-01T00:00:00Z",
        "to_date": "2021-02-01T00:00:00Z",
        "run_backwards": False,
        "dag_run_conf": {},
        "reprocess_behavior": "completed",
        "max_active_runs": 3,
    }
    assert calls[0][3] == "TOKEN"


def test_wait_for_backfill_waits_until_complete(
    monkeypatch,
):
    """Backfill polling stops when Airflow completes it."""
    responses = [
        {"completed_at": None},
        {"completed_at": "2026-10-02T12:00:00Z"},
    ]

    monkeypatch.setattr(
        "meridian.operational.pipeline.request",
        lambda *args, **kwargs: responses.pop(0),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.time.sleep",
        lambda seconds: None,
    )

    _wait_for_backfill(7, "TOKEN")

    assert responses == []


def test_months_in_range_crosses_year():
    """Month ranges work across a year boundary."""
    assert _months_in_range(
        "2021-11",
        "2022-02",
    ) == [
        "2021-11",
        "2021-12",
        "2022-01",
        "2022-02",
    ]


def test_parse_args_reads_market_only():
    """CLI parser accepts a market without a month."""
    args = parse_args(["jc"])

    assert args.market == "jc"
    assert args.start_month is None
    assert args.end_month is None


def test_parse_args_reads_named_month():
    """CLI parser accepts a market and named month."""
    args = parse_args(
        ["jc", "2026-06"]
    )

    assert args.market == "jc"
    assert args.start_month == "2026-06"
    assert args.end_month is None


def test_parse_args_reads_month_range():
    """CLI parser accepts a market and month range."""
    args = parse_args(
        [
            "jc",
            "2021-01",
            "2021-02",
        ]
    )

    assert args.market == "jc"
    assert args.start_month == "2021-01"
    assert args.end_month == "2021-02"


def test_run_cli_passes_arguments_to_pipeline(
    monkeypatch,
):
    """CLI arguments are passed to the pipeline."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.pipeline.parse_args",
        lambda: parse_args(
            ["jc", "2026-06"]
        ),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.run_pipeline",
        lambda *args: calls.append(args),
    )

    run_cli()

    assert calls == [
        ("jc", "2026-06", None)
    ]