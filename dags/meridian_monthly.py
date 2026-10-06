import os
from datetime import datetime, timedelta
import psycopg
from airflow.sdk import PokeReturnValue, chain, dag, task
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.sdk.exceptions import AirflowSkipException

from meridian.operational.config import EARLIEST, JOBS, MARKETS
from meridian.operational.job_runner import call_bronze, call_silver
from meridian.operational.gold_batch import run_gold_batch
from meridian.operational.publication import is_published
from meridian.operational.progress import month_is_complete


def create_market_dag(market: str):
    job = JOBS[market]
    earliest = EARLIEST[job]
    start_date = datetime.strptime(earliest, "%Y-%m")

    @dag(
        dag_id=f"meridian_{market}_monthly",
        schedule=CronDataIntervalTimetable("0 0 1 * *", timezone="UTC",),
        start_date=start_date,
        catchup=True,
        max_active_runs=3,
        default_args={"retries": 2, "owner": "data-eng"},
        params={"month": ""},
        tags=["meridian", market, "monthly"],
    )
    def meridian_monthly():
        @task
        def window(params=None, data_interval_start=None, data_interval_end=None,) -> str:
            """Resolve the Airflow run window to a YYYY-MM month."""
            params = params or {}

            if params.get("month"):
                return params["month"]

            if (data_interval_start is None or data_interval_end is None):
                raise ValueError(
                    "No window provided. A manual trigger has no data interval."
                )

            return data_interval_start.strftime("%Y-%m")
        
        @task(retries=0)
        def should_process(month: str, dag_run=None) -> None:
            """Validate the month and skip complete scheduled runs."""
            if month < earliest:
                raise ValueError(
                    f"Month {month} is before earliest {earliest}"
                )

            if dag_run.run_type != "scheduled":
                return

            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                complete = month_is_complete(conn, job, market, month,)

            if complete:
                raise AirflowSkipException(
                    f"{market} {month} is already complete"
                )

        @task.sensor(poke_interval=60, timeout=timedelta(hours=1), mode="reschedule",)
        def publication(month: str) -> PokeReturnValue:
            """Wait until source data for the month is published."""
            published = is_published(market, month)

            return PokeReturnValue(is_done=published)

        @task
        def bronze(month: str) -> None:
            """Run and record the Bronze job."""
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                call_bronze(conn, job, month,)


        @task
        def silver(month: str) -> None:
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                call_silver(conn, job, month)

        @task
        def gold(month: str) -> None:
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                run_gold_batch(conn, job, market, month,)

        month = window()

        process_task = should_process(month)
        publication_task = publication(month)
        bronze_task = bronze(month)
        silver_task = silver(month)
        gold_task = gold(month)

        chain(process_task, publication_task, bronze_task, silver_task, gold_task)

    return meridian_monthly()


for market in MARKETS:
    globals()[f"meridian_{market}_monthly"] = create_market_dag(market)