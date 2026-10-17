
import pytest
import csv

from meridian.transform_to_silver.database import insert_silver_rejects
from meridian.transform_to_silver.transform import transform_file


GOOD = {
    "market": "jc",
    "data_window": "2026-06",
    "started_at": "2026-06-02 08:00:00",
    "ended_at": "2026-06-02 08:15:00",
    "start_station_id": "JC115",
    "end_station_id": None,
    "start_station_name": "Grove St PATH",
    "end_station_name": None,
    "start_lat": None,
    "start_lng": None,
    "end_lat": None,
    "end_lng": None,
    "reason": "never docked",
    "raw_row": {
        "ride_id": "test-ride-001",
        "started_at": "2026-06-02 08:00:00",
        "ended_at": "2026-06-02 08:15:00",
        "start_station_id": "JC115",
        "end_station_id": "",
        "start_station_name": "Grove St PATH",
        "end_station_name": "",
        "start_lat": "",
        "start_lng": "",
        "end_lat": "",
        "end_lng": "",
    },
}


def write_csv(path, row):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)


def test_reject_preserves_raw_source(conn):
    """A rejected ride must retain its original source fields."""
    with conn.transaction():
        insert_silver_rejects(conn, [GOOD])

        row = conn.execute(
            """
            SELECT reason, raw_row
            FROM silver_rejects
            WHERE market = %s AND data_window = %s
            """,
            (GOOD["market"], GOOD["data_window"]),
        ).fetchone()

        assert row is not None
        assert row[0] == GOOD["reason"]
        assert row[1] == GOOD["raw_row"]




def test_transform_preserves_rejected_source(tmp_path):
    """A rejected CSV row retains its original fields."""
    csv_file = tmp_path / "rides.csv"
    write_csv(csv_file, GOOD["raw_row"])

    valid, rejects = transform_file(csv_file, "jc", "2026-06")

    assert valid == []
    assert len(rejects) == 1
    assert rejects[0]["reason"] == GOOD["reason"]
    assert rejects[0]["raw_row"] == GOOD["raw_row"]



@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("started_at", "invalid start time"),
        ("ended_at", "invalid end time"),
    ],
)
def test_invalid_timestamp_is_quarantined(tmp_path, field, reason):
    row = GOOD["raw_row"].copy()
    row["end_station_id"] = "JC116"
    row[field] = "not-a-date"
    csv_file = tmp_path / "invalid.csv"
    write_csv(csv_file, row)
    valid, rejects = transform_file(csv_file, "jc", "2026-06")
    assert valid == []
    assert len(rejects) == 1
    assert rejects[0]["reason"] == reason
    assert rejects[0]["raw_row"][field] == "not-a-date"


def test_legacy_timestamp_is_accepted(tmp_path):
    row = {
        "starttime": "2019-06-02 08:00:00.0000",
        "stoptime": "2019-06-02 08:15:00.0000",
        "start station id": "JC115",
        "end station id": "JC116",
        "start station name": "Grove St PATH",
        "end station name": "Newport",
        "start station latitude": "40.7",
        "start station longitude": "-74.0",
        "end station latitude": "40.7",
        "end station longitude": "-74.0",
    }
    csv_file = tmp_path / "legacy.csv"
    write_csv(csv_file, row)
    valid, rejects = transform_file(csv_file, "jc", "2019-06")
    assert len(valid) == 1
    assert rejects == []
