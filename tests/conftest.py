import subprocess

import pytest


@pytest.fixture
def stack_is_running():
    subprocess.run(
        ["just", "up"],
        check=True,
    )

@pytest.fixture
def bronze_jc_2019_06(stack_is_running):
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:jc",
            "2019-06",
        ],
        check=True,
    )

@pytest.fixture
def bronze_jc_2026_06(stack_is_running):
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:jc",
            "2026-06",
        ],
        check=True,
    )

@pytest.fixture
def bronze_nyc_2018_04(stack_is_running):
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:nyc",
            "2018-04",
        ],
        check=True,
    )

@pytest.fixture
def bronze_jc_2019_06_again(bronze_jc_2019_06):
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:jc",
            "2019-06",
        ],
        check=True,
    )

@pytest.fixture
def bronze_jc_2021_02(stack_is_running):
    subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:jc",
            "2021-02",
        ],
        check=True,
    )