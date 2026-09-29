import pytest

from meridian.operational.pipeline import run_pipeline


GOOD = {"job": "trips:jc", "market": "jc", "month": "2021-02",}


def test_pipeline_runs_all_stages_in_order(
    pipeline_stage_spies,
):
    run_pipeline(
        GOOD["market"],
        GOOD["month"],
    )

    assert pipeline_stage_spies == [
        ("bronze", GOOD["job"], GOOD["month"]),
        ("silver", GOOD["job"], GOOD["month"]),
        ("gold", GOOD["job"], GOOD["month"]),
    ]


def test_pipeline_runs_next_due_month_when_no_month_is_given(
    monkeypatch,
    pipeline_stage_spies,
    migrated,
):
    monkeypatch.setattr(
        "meridian.operational.pipeline.progress",
        lambda conn, job: {"next": "2021-02"},
    )

    run_pipeline(GOOD["market"])

    assert pipeline_stage_spies == [
        ("bronze", GOOD["job"], "2021-02"),
        ("silver", GOOD["job"], "2021-02"),
        ("gold", GOOD["job"], "2021-02"),
    ]


def test_pipeline_does_nothing_when_no_month_is_due(
    monkeypatch,
    pipeline_stage_spies,
    migrated,
):
    monkeypatch.setattr(
        "meridian.operational.pipeline.progress",
        lambda conn, job: {"next": None},
    )

    run_pipeline(GOOD["market"])

    assert pipeline_stage_spies == []


def test_pipeline_runs_every_month_in_range(
    pipeline_stage_spies,
):
    run_pipeline(
        GOOD["market"],
        "2021-01",
        "2021-03",
    )

    assert pipeline_stage_spies == [
        ("bronze", GOOD["job"], "2021-01"),
        ("silver", GOOD["job"], "2021-01"),
        ("gold", GOOD["job"], "2021-01"),
        ("bronze", GOOD["job"], "2021-02"),
        ("silver", GOOD["job"], "2021-02"),
        ("gold", GOOD["job"], "2021-02"),
        ("bronze", GOOD["job"], "2021-03"),
        ("silver", GOOD["job"], "2021-03"),
        ("gold", GOOD["job"], "2021-03"),
    ]


def test_pipeline_runs_named_complete_month(
    pipeline_stage_spies,
):
    run_pipeline(
        GOOD["market"],
        GOOD["month"],
    )

    assert pipeline_stage_spies != []


def test_pipeline_rejects_month_before_earliest(
    pipeline_stage_spies,
):
    with pytest.raises(ValueError):
        run_pipeline(
            GOOD["market"],
            "2020-12",
        )

    assert pipeline_stage_spies == []


def test_pipeline_rejects_range_before_earliest(
    pipeline_stage_spies,
):
    with pytest.raises(ValueError):
        run_pipeline(
            GOOD["market"],
            "2020-12",
            "2021-02",
        )

    assert pipeline_stage_spies == []


def test_pipeline_rejects_range_when_start_is_after_end(
    pipeline_stage_spies,
):
    with pytest.raises(ValueError):
        run_pipeline(
            GOOD["market"],
            "2021-03",
            "2021-01",
        )

    assert pipeline_stage_spies == []


def test_pipeline_rejects_invalid_market(
    pipeline_stage_spies,
):
    with pytest.raises(ValueError):
        run_pipeline(
            "bad",
            GOOD["month"],
        )

    assert pipeline_stage_spies == []


def test_pipeline_stops_when_stage_fails(
    monkeypatch,
    pipeline_stage_spies,
):
    def fail_silver(job, month):
        raise RuntimeError("silver failed")

    monkeypatch.setattr(
        "meridian.operational.pipeline._run_silver",
        fail_silver,
    )

    with pytest.raises(RuntimeError, match="silver failed"):
        run_pipeline(
            GOOD["market"],
            GOOD["month"],
        )

    assert pipeline_stage_spies == [
        ("bronze", GOOD["job"], GOOD["month"]),
    ]