import subprocess
import sys

from meridian.ingest_to_bronze.main import main as bronze_main
from meridian.ingest_to_bronze.main import parse_dataset_market
from meridian.operational.control import record_job_attempt


def _run_container(module: str, job: str, month: str) -> None:
    """Run an existing Stage 1 job in the app container."""
    subprocess.run(
        [  "docker",
            "compose",
            "-p",
            "meridian",
            "run",
            "--rm",
            "--no-deps",
            "app",
            "uv",
            "run",
            "python",
            "-m",
            module,
            job,
            month,
        ],
        cwd="/opt/airflow/project",
        check=True,
    )

def run_bronze(job: str, month: str) -> None:
    """Run the existing Stage 1 Bronze job in-process."""
    original_argv = sys.argv
    try:
        sys.argv = ["ingest-to-bronze", job, month]
        bronze_main()
    finally:
        sys.argv = original_argv
# def run_bronze(job: str, month: str) -> None:
#     """Run the existing Stage 1 Bronze job in its container."""
#     _run_container(
#         "meridian.ingest_to_bronze.main",
#         job,
#         month,
#     )


def run_silver(job: str, month: str) -> None:
    """Run the existing Stage 1 Silver job in its container."""
    _run_container(
        "meridian.transform_to_silver.main",
        job,
        month,
    )


def _record_attempt(
    conn,
    layer: str,
    job: str,
    market: str,
    month: str,
    status: str,
) -> None:
    """Record one completed job attempt."""
    record_job_attempt(
        conn,
        layer,
        job,
        market.lower(),
        month,
        status,
    )
    conn.commit()


def _call_job(conn, runner, layer: str, job: str, month: str) -> None:
    """Run and record one completed job attempt."""
    _, market = parse_dataset_market(job)
    try:
        runner(job, month)
    except Exception:
        _record_attempt(conn, layer, job, market, month, "FAILED")
        raise
    _record_attempt(conn, layer, job, market, month, "SUCCESS")


def call_bronze(conn, job: str, month: str) -> None:
    """Run one Bronze window at a time and record the attempt."""
    _lock_window(conn, job, month)
    _call_job(conn, run_bronze, "bronze", job, month)


def _lock_window(conn, job: str, month: str) -> None:
    """Serialize concurrent work for the same job window."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
            (job, month),
        )

def call_silver(conn, job: str, month: str) -> None:
    """Run one Silver window at a time and record the attempt."""
    _lock_window(conn, job, month)
    _call_job(conn, run_silver, "silver", job, month)