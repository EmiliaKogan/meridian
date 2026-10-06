import json
from pathlib import Path

import pytest

from meridian.inspect.main import (
    inspect_bronze,
    inspect_coverage,
    inspect_runs,
    inspect_silver,
    parse_dataset_market,
)


GOOD = {
    "job": "trips:jc",
    "market": "JC",
    "window": "2026-06",
}


# ------------------------------------------------------------------
# Stage 1
# ------------------------------------------------------------------


def test_parse_dataset_market():
    """A valid job is split into dataset and market."""
    assert parse_dataset_market(GOOD["job"]) == (
        "trips",
        GOOD["market"],
    )


def test_parse_dataset_market_rejects_dataset():
    """An unknown dataset is rejected."""
    with pytest.raises(ValueError, match="Unknown dataset"):
        parse_dataset_market("rides:jc")


def test_parse_dataset_market_rejects_market():
    """An unknown market is rejected."""
    with pytest.raises(ValueError, match="Unknown market"):
        parse_dataset_market("trips:bad")


def test_inspect_bronze_reports_files(
    tmp_path,
    monkeypatch,
    capsys,
):
    """Bronze inspect reports objects and data rows."""
    bronze = tmp_path / "JC" / "2026" / "06"
    bronze.mkdir(parents=True)

    (bronze / "one.csv").write_text(
        "id,name\n1,a\n2,b\n",
        encoding="utf-8",
    )
    (bronze / "two.csv").write_text(
        "id,name\n3,c\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "meridian.inspect.main.Path",
        lambda value: tmp_path,
    )

    inspect_bronze(
        GOOD["market"],
        GOOD["window"],
    )

    result = json.loads(capsys.readouterr().out)

    assert result == {
        "layer": "bronze",
        "job": GOOD["job"],
        "window": GOOD["window"],
        "objects": 2,
        "rows": 3,
    }


def test_inspect_silver_reports_rows(
    monkeypatch,
    capsys,
):
    """Silver inspect reports rows and reject reasons."""
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            pass

        def fetchone(self):
            return (12,)

        def fetchall(self):
            return [
                ("bad_station", 2),
                ("bad_time", 1),
            ]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return Cursor()

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test",
    )
    monkeypatch.setattr(
        "meridian.inspect.main.psycopg.connect",
        lambda url: Connection(),
    )

    inspect_silver(
        GOOD["market"],
        GOOD["window"],
    )

    result = json.loads(capsys.readouterr().out)

    assert result == {
        "layer": "silver",
        "job": GOOD["job"],
        "window": GOOD["window"],
        "rows": 12,
        "rejects": 3,
        "reasons": {
            "bad_station": 2,
            "bad_time": 1,
        },
    }


# ------------------------------------------------------------------
# Stage 2 coverage
# ------------------------------------------------------------------


def test_inspect_coverage_reports_progress(
    monkeypatch,
    capsys,
):
    """Coverage inspect prints the progress contract."""
    expected = {
        "job": GOOD["job"],
        "earliest": "2021-01",
        "watermark": "2021-02",
        "complete": 3,
        "gaps": ["2021-03"],
        "next": "2021-03",
    }

    monkeypatch.setattr(
        "meridian.inspect.main._load_progress",
        lambda job: expected,
    )

    inspect_coverage(GOOD["job"])

    assert json.loads(capsys.readouterr().out) == expected


def test_inspect_coverage_rejects_unknown_job():
    """Coverage rejects an unknown job."""
    with pytest.raises(ValueError, match="Unknown job"):
        inspect_coverage("trips:bad")


# ------------------------------------------------------------------
# Stage 2 runs
# ------------------------------------------------------------------


def test_inspect_runs_reports_airflow_runs(
    monkeypatch,
    capsys,
):
    """Runs inspect prints the required Airflow run contract."""
    expected = {
        "market": "jc",
        "runs": [
            {
                "month": "2026-06",
                "type": "manual",
                "state": "success",
                "tasks": {
                    "ingest-to-bronze trips:jc 2026-06": {
                        "state": "success",
                        "tries": 1,
                    },
                    "transform-to-silver trips:jc 2026-06": {
                        "state": "success",
                        "tries": 2,
                    },
                    "transform-to-gold station-daily": {
                        "state": "success",
                        "tries": 1,
                        "days": 30,
                        "failed_days": [],
                    },
                },
            }
        ],
    }

    monkeypatch.setattr(
        "meridian.inspect.main._load_airflow_runs",
        lambda market: expected["runs"],
    )

    inspect_runs("jc")

    assert json.loads(capsys.readouterr().out) == expected


def test_inspect_runs_rejects_unknown_market():
    """Runs rejects an unknown market."""
    with pytest.raises(ValueError, match="Unknown market"):
        inspect_runs("bad")


def test_run_month_prefers_manual_conf():
    """A manual run month comes from DAG run configuration."""
    from meridian.inspect.main import _run_month

    run = {
        "conf": {"month": "2026-06"},
        "data_interval_start": None,
    }

    assert _run_month(run) == "2026-06"


def test_run_month_uses_data_interval():
    """A scheduled or backfill month comes from its interval."""
    from meridian.inspect.main import _run_month

    run = {
        "conf": {},
        "data_interval_start": "2021-02-01T00:00:00Z",
    }

    assert _run_month(run) == "2021-02"


def test_airflow_run_uses_airflow_type_and_state(
    monkeypatch,
):
    """Run type and state use Airflow's own values."""
    from meridian.inspect.main import _airflow_run_result

    run = {
        "dag_run_id": "manual__test",
        "run_type": "manual",
        "state": "success",
        "conf": {"month": "2026-06"},
        "data_interval_start": None,
    }

    monkeypatch.setattr(
        "meridian.inspect.main._load_task_results",
        lambda market, run_id, month: {},
    )

    result = _airflow_run_result("jc", run)

    assert result["type"] == "manual"
    assert result["state"] == "success"


def test_task_results_use_airflow_states_and_tries(
    monkeypatch,
):
    """Task summaries use Airflow task states and try numbers."""
    from meridian.inspect.main import _load_task_results

    response = {
        "task_instances": [
            {
                "task_id": "bronze",
                "state": "success",
                "try_number": 1,
            },
            {
                "task_id": "silver",
                "state": "success",
                "try_number": 2,
            },
            {
                "task_id": "gold",
                "state": "success",
                "try_number": 1,
            },
        ]
    }

    monkeypatch.setattr(
        "meridian.inspect.main.request",
        lambda *args, **kwargs: response,
    )
    monkeypatch.setattr(
        "meridian.inspect.main.token",
        lambda: "TOKEN",
    )
    monkeypatch.setattr(
        "meridian.inspect.main._gold_summary",
        lambda market, month: {
            "days": 30,
            "failed_days": [],
        },
    )

    result = _load_task_results(
        "jc",
        "manual__test",
        "2026-06",
    )

    assert result == {
        "ingest-to-bronze trips:jc 2026-06": {
            "state": "success",
            "tries": 1,
        },
        "transform-to-silver trips:jc 2026-06": {
            "state": "success",
            "tries": 2,
        },
        "transform-to-gold station-daily": {
            "state": "success",
            "tries": 1,
            "days": 30,
            "failed_days": [],
        },
    }