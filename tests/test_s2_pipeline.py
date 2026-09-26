import pytest
from pathlib import Path
from datetime import date
from unittest.mock import MagicMock
from meridian.operational.pipeline import _run_bronze, _run_silver, _run_gold, _run_gold_day, run_pipeline

GOOD = {"market": "jc", "month": "2021-06",}

######## Validation #########
def test_pipeline_rejects_unknown_market():
    with pytest.raises(ValueError):
        run_pipeline("unknown")


def test_pipeline_rejects_month_before_earliest():
    with pytest.raises(ValueError):
        run_pipeline(GOOD["market"], "2020-12",)


def test_pipeline_rejects_invalid_month_format():
    with pytest.raises(ValueError):
        run_pipeline(GOOD["market"], "2021-6", )


def test_pipeline_rejects_invalid_month():
    with pytest.raises(ValueError):
        run_pipeline(GOOD["market"], "2021-13",)


def test_pipeline_rejects_reversed_range():
    with pytest.raises(ValueError):
        run_pipeline(GOOD["market"], "2021-06", "2021-01",)


######## Execution #########
def test_pipeline_runs_stages_in_order(pipeline_stage_spies):
    run_pipeline(GOOD["market"], GOOD["month"])

    assert pipeline_stage_spies  == [
        ("bronze", "trips:jc", "2021-06"),
        ("silver", "trips:jc", "2021-06"),
        ("gold", "2021-06"),
    ]


def test_pipeline_runs_month_range(pipeline_stage_spies):
    run_pipeline("jc", "2021-06", "2021-08")

    assert pipeline_stage_spies  == [
        ("bronze", "trips:jc", "2021-06"),
        ("silver", "trips:jc", "2021-06"),
        ("gold", "2021-06"),
        ("bronze", "trips:jc", "2021-07"),
        ("silver", "trips:jc", "2021-07"),
        ("gold", "2021-07"),
        ("bronze", "trips:jc", "2021-08"),
        ("silver", "trips:jc", "2021-08"),
        ("gold", "2021-08"),
    ]

def test_pipeline_skips_when_nothing_is_due(pipeline_stage_spies, monkeypatch,):
    monkeypatch.setattr("meridian.operational.pipeline.progress", lambda conn, job: {"next": None}, )

    run_pipeline("jc")

    assert pipeline_stage_spies == []


def test_run_bronze_runs_stage1_flow(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "meridian.operational.pipeline.find_source_zip",
        lambda market, month: calls.append(
            ("find_source_zip", market, month)
        ) or "source.zip",
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.download_source_zip",
        lambda source_zip: calls.append(
            ("download_source_zip", source_zip)
        ) or Path("tmp/source.zip"),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.find_latest_csvs_in_zip",
        lambda zip_path, market, month: calls.append(
            ("find_latest_csvs", market, month)
        ) or ["rides.csv"],
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.save_bronze_csvs",
        lambda zip_path, csv_paths, market, month: calls.append(
            ("save_bronze_csvs", market, month)
        ),
    )

    _run_bronze("trips:jc", "2021-06")

    assert calls == [
        ("find_source_zip", "JC", "2021-06"),
        ("download_source_zip", "source.zip"),
        ("find_latest_csvs", "JC", "2021-06"),
        ("save_bronze_csvs", "JC", "2021-06"),
    ]

def test_run_silver_runs_stage1_command(monkeypatch):
    calls = []

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr("meridian.operational.pipeline.subprocess.run", fake_run,)

    _run_silver("trips:jc", "2021-06")

    assert calls == [
        (
            [
                "just",
                "run",
                "transform-to-silver",
                "trips:jc",
                "2021-06",
            ],
            True,
        )
    ]

def test_run_gold_runs_every_day_of_month(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "meridian.operational.pipeline._run_gold_day",
        lambda conn, target_date: calls.append(target_date),
    )

    _run_gold(None, "2021-02")

    assert len(calls) == 28


def test_run_gold_day_runs_stage1_gold(monkeypatch):
    calls = []
    conn = MagicMock()

    monkeypatch.setattr(
        "meridian.operational.pipeline.delete_day",
        lambda conn, target_date: calls.append(
            ("delete_day", target_date)
        ),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.insert_date",
        lambda conn, date_row: calls.append(
            ("insert_date", date_row)
        ),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.insert_stations",
        lambda conn, target_date: calls.append(
            ("insert_stations", target_date)
        ),
    )
    monkeypatch.setattr(
        "meridian.operational.pipeline.insert_events",
        lambda conn, target_date: calls.append(
            ("insert_events", target_date)
        ),
    )

    _run_gold_day(conn, date(2021, 2, 1))

    assert [call[0] for call in calls] == [
        "delete_day",
        "insert_date",
        "insert_stations",
        "insert_events",
    ]
    conn.commit.assert_called_once()