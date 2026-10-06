import csv
import json
import os
import sys
from pathlib import Path

import psycopg

from meridian.operational.client import dag_id, request, token
from meridian.operational.config import EARLIEST, MARKETS
from meridian.operational.progress import progress


def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)
    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")
    market = market.upper()
    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")
    return dataset, market


def inspect_bronze(market: str, data_window: str) -> None:
    year, month = data_window.split("-")
    bronze_dir = Path("/data/bronze") / market / year / month
    csv_files = sorted(bronze_dir.glob("*.csv"))
    total_rows = 0
    for csv_file in csv_files:
        with csv_file.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            next(reader, None)
            total_rows += sum(1 for _ in reader)
    result = {
        "layer": "bronze",
        "job": f"trips:{market.lower()}",
        "window": data_window,
        "objects": len(csv_files),
        "rows": total_rows,
    }
    print(json.dumps(result))


def _silver_rows(cur, market: str, data_window: str) -> int:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM silver_rides
        WHERE market = %s
          AND data_window = %s
        """,
        (market, data_window),
    )
    return cur.fetchone()[0]


def _silver_reasons(cur, market: str, data_window: str) -> dict:
    cur.execute(
        """
        SELECT reason, COUNT(*)
        FROM silver_rejects
        WHERE market = %s
          AND data_window = %s
        GROUP BY reason
        ORDER BY reason
        """,
        (market, data_window),
    )
    return dict(cur.fetchall())


def inspect_silver(market: str, data_window: str) -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            rows = _silver_rows(cur, market, data_window)
            reasons = _silver_reasons(cur, market, data_window)
    result = {
        "layer": "silver",
        "job": f"trips:{market.lower()}",
        "window": data_window,
        "rows": rows,
        "rejects": sum(reasons.values()),
        "reasons": reasons,
    }
    print(json.dumps(result))


def _validate_job(job: str) -> None:
    if job not in EARLIEST:
        raise ValueError(f"Unknown job: {job}")


def _validate_market(market: str) -> None:
    if market.lower() not in MARKETS:
        raise ValueError(f"Unknown market: {market}")


def _load_progress(job: str) -> dict:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return progress(conn, job)


def inspect_coverage(job: str) -> None:
    _validate_job(job)
    print(json.dumps(_load_progress(job)))


def _run_month(run: dict) -> str:
    conf = run.get("conf") or {}
    if conf.get("month"):
        return conf["month"]
    interval = run.get("data_interval_start")
    if not interval:
        raise ValueError("Airflow run has no month")
    return interval[:7]


def _task_name(task_id: str, market: str, month: str) -> str:
    names = {
        "bronze": f"ingest-to-bronze trips:{market} {month}",
        "silver": f"transform-to-silver trips:{market} {month}",
        "gold": "transform-to-gold station-daily",
    }
    return names[task_id]


def _gold_summary(market: str, month: str) -> dict:
    query = """
        SELECT load_window, status
        FROM control_table
        WHERE layer = 'gold'
          AND market = %s
          AND load_window LIKE %s
        ORDER BY finished_at
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (market, f"{month}-%"))
            rows = cur.fetchall()
    return _summarize_gold(rows)


def _summarize_gold(rows: list[tuple]) -> dict:
    latest = {}
    for window, status in rows:
        latest[window] = status
    failed = sorted(
        day for day, status in latest.items()
        if status == "FAILED"
    )
    return {
        "days": len(latest),
        "failed_days": failed,
    }


def _task_result(task: dict) -> dict:
    return {
        "state": task["state"],
        "tries": task["try_number"],
    }


def _add_task(
    results: dict,
    task: dict,
    market: str,
    month: str,
) -> None:
    task_id = task["task_id"]
    if task_id not in {"bronze", "silver", "gold"}:
        return
    name = _task_name(task_id, market, month)
    results[name] = _task_result(task)
    if task_id == "gold":
        results[name].update(_gold_summary(market, month))


def _load_task_results(
    market: str,
    run_id: str,
    month: str,
) -> dict:
    path = (
        f"/api/v2/dags/{dag_id(market)}"
        f"/dagRuns/{run_id}/taskInstances"
    )
    data = request("GET", path, token=token())
    results = {}
    for task in data.get("task_instances", []):
        _add_task(results, task, market, month)
    return results


def _airflow_run_result(market: str, run: dict) -> dict:
    month = _run_month(run)
    return {
        "month": month,
        "type": run["run_type"],
        "state": run["state"],
        "tasks": _load_task_results(
            market,
            run["dag_run_id"],
            month,
        ),
    }


def _load_airflow_runs(market: str) -> list[dict]:
    path = (
        f"/api/v2/dags/{dag_id(market)}"
        "/dagRuns?order_by=-logical_date"
    )
    data = request("GET", path, token=token())
    return [
        _airflow_run_result(market, run)
        for run in data.get("dag_runs", [])
    ]


def inspect_runs(market: str) -> None:
    market = market.lower()
    _validate_market(market)
    result = {
        "market": market,
        "runs": _load_airflow_runs(market),
    }
    print(json.dumps(result))


def _inspect_stage_one(args: list[str]) -> None:
    layer, job, data_window = args
    _, market = parse_dataset_market(job)
    if layer == "bronze":
        inspect_bronze(market, data_window)
    elif layer == "silver":
        inspect_silver(market, data_window)
    else:
        raise ValueError(f"Unknown layer: {layer}")


def main() -> None:
    command = sys.argv[1]
    if command == "coverage":
        inspect_coverage(sys.argv[2])
    elif command == "runs":
        inspect_runs(sys.argv[2])
    else:
        _inspect_stage_one(sys.argv[1:4])


if __name__ == "__main__":
    main()