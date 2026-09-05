import json
import subprocess


def test_bronze_jc_2019_06_ingestion_succeeds(stack_is_running):
    result = subprocess.run(
        [
            "just",
            "run",
            "ingest-to-bronze",
            "trips:jc",
            "2019-06",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_bronze_jc_2019_06_has_expected_row_count(
    bronze_jc_2019_06,
):
    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:jc",
            "2019-06",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    output = json.loads(result.stdout)

    assert output["rows"] == 39430


def test_bronze_jc_2026_06_has_expected_row_count(
    bronze_jc_2026_06,
):
    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:jc",
            "2026-06",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    output = json.loads(result.stdout)

    assert output["rows"] == 109897


def test_bronze_nyc_2018_04_has_expected_row_count(
    bronze_nyc_2018_04,
):
    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:nyc",
            "2018-04",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    output = json.loads(result.stdout)

    assert output["rows"] == 1307543


def test_bronze_jc_2019_06_is_idempotent(
    bronze_jc_2019_06_again,
):
    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:jc",
            "2019-06",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)

    assert output["rows"] == 39430


def test_bronze_jc_2019_06_is_unchanged_after_2026_ingestion(
    bronze_jc_2019_06,
):
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

    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:jc",
            "2019-06",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)

    assert output["rows"] == 39430


def test_bronze_jc_2021_02_ingestion_succeeds(
    bronze_jc_2021_02,
):
    result = subprocess.run(
        [
            "just",
            "inspect",
            "bronze",
            "trips:jc",
            "2021-02",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)

    assert output["rows"] > 0