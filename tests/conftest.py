import os
import subprocess
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Start a temporary PostgreSQL container and yield its connection URL."""
    with PostgresContainer("postgres:16-alpine", driver=None) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated(pg_url: str) -> str:
    """Apply all Alembic migrations to the test database."""
    os.environ["DATABASE_URL"] = pg_url

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    return pg_url


@pytest.fixture
def database_connection(migrated: str):
    """Provide a connection to the migrated test database."""
    with psycopg.connect(migrated) as conn:
        yield conn


@pytest.fixture
def stack_is_running():
    subprocess.run(["just", "up"], check=True)


@pytest.fixture
def bronze_jc_2019_06(stack_is_running):
    subprocess.run(
        ["just", "run", "ingest-to-bronze", "trips:jc", "2019-06"],
        check=True,
    )


@pytest.fixture
def bronze_jc_2026_06(stack_is_running):
    subprocess.run(
        ["just", "run", "ingest-to-bronze", "trips:jc", "2026-06"],
        check=True,
    )


@pytest.fixture
def bronze_nyc_2018_04(stack_is_running):
    subprocess.run(
        ["just", "run", "ingest-to-bronze", "trips:nyc", "2018-04"],
        check=True,
    )


@pytest.fixture
def bronze_jc_2019_06_again(bronze_jc_2019_06):
    subprocess.run(
        ["just", "run", "ingest-to-bronze", "trips:jc", "2019-06"],
        check=True,
    )


@pytest.fixture
def bronze_jc_2021_02(stack_is_running):
    subprocess.run(
        ["just", "run", "ingest-to-bronze", "trips:jc", "2021-02"],
        check=True,
    )



# import subprocess
# import pytest



# @pytest.fixture
# def stack_is_running():
#     subprocess.run(
#         ["just", "up"],
#         check=True,
#     )



# @pytest.fixture
# def bronze_jc_2019_06(stack_is_running):
#     subprocess.run(
#         [
#             "just",
#             "run",
#             "ingest-to-bronze",
#             "trips:jc",
#             "2019-06",
#         ],
#         check=True,
#     )

# @pytest.fixture
# def bronze_jc_2026_06(stack_is_running):
#     subprocess.run(
#         [
#             "just",
#             "run",
#             "ingest-to-bronze",
#             "trips:jc",
#             "2026-06",
#         ],
#         check=True,
#     )

# @pytest.fixture
# def bronze_nyc_2018_04(stack_is_running):
#     subprocess.run(
#         [
#             "just",
#             "run",
#             "ingest-to-bronze",
#             "trips:nyc",
#             "2018-04",
#         ],
#         check=True,
#     )

# @pytest.fixture
# def bronze_jc_2019_06_again(bronze_jc_2019_06):
#     subprocess.run(
#         [
#             "just",
#             "run",
#             "ingest-to-bronze",
#             "trips:jc",
#             "2019-06",
#         ],
#         check=True,
#     )

# @pytest.fixture
# def bronze_jc_2021_02(stack_is_running):
#     subprocess.run(
#         [
#             "just",
#             "run",
#             "ingest-to-bronze",
#             "trips:jc",
#             "2021-02",
#         ],
#         check=True,
#     )