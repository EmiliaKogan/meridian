
from meridian.operational.control import record_load

GOOD = {"job": "trips:jc", "market": "jc", "window": "2021-01",}

def test_successful_load_is_recorded(database_connection):
    record_load(database_connection, GOOD["job"], GOOD["market"], GOOD["window"],)

    database_connection.commit()

    with database_connection.cursor() as cur:
        cur.execute(
            """
            SELECT job, market, load_window
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )

        row = cur.fetchone()

    assert row == (GOOD["job"], GOOD["market"], GOOD["window"],)

def test_recording_same_load_twice_creates_one_record(database_connection):
    record_load(database_connection, GOOD["job"], GOOD["market"], GOOD["window"],) # first run
    record_load(database_connection, GOOD["job"], GOOD["market"], GOOD["window"],) # second run

    database_connection.commit()

    with database_connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )
        count = cur.fetchone()[0]
        
    assert count == 1

def test_successful_load_has_loaded_at(database_connection):
    record_load(database_connection, GOOD["job"], GOOD["market"], GOOD["window"],)

    database_connection.commit()

    with database_connection.cursor() as cur:
        cur.execute(
            """
            SELECT loaded_at
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (
                GOOD["job"],
                GOOD["market"],
                GOOD["window"],
            ),
        )
        loaded_at = cur.fetchone()[0]

    assert loaded_at is not None

def test_recording_same_load_updates_loaded_at(conn):
    record_load(conn,GOOD["job"],GOOD["market"],GOOD["window"],)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT loaded_at
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (GOOD["job"], GOOD["market"], GOOD["window"]),
        )
        first_loaded_at = cur.fetchone()[0]

    record_load(conn,GOOD["job"],GOOD["market"],GOOD["window"],)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT loaded_at
            FROM operational_loads
            WHERE job = %s
              AND market = %s
              AND load_window = %s
            """,
            (GOOD["job"], GOOD["market"], GOOD["window"]),
        )
        second_loaded_at = cur.fetchone()[0]

    assert second_loaded_at > first_loaded_at