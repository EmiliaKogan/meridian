import csv
from pathlib import Path

def empty_to_none(value):
    return None if value == "" else value

def conform_new(row: dict, market: str, data_window: str) -> dict:
    return {
        "market": market,
        "data_window": data_window,
        "started_at": empty_to_none(row["started_at"]),
        "ended_at": empty_to_none(row["ended_at"]),
        "start_station_id": empty_to_none(row["start_station_id"]),
        "end_station_id": empty_to_none(row["end_station_id"]),
        "start_station_name": empty_to_none(row["start_station_name"]),
        "end_station_name": empty_to_none(row["end_station_name"]),
        "start_lat": empty_to_none(row["start_lat"]),
        "start_lng": empty_to_none(row["start_lng"]),
        "end_lat": empty_to_none(row["end_lat"]),
        "end_lng": empty_to_none(row["end_lng"]),
    }

def conform_old(row: dict, market: str, data_window: str) -> dict:
    return {
        "market": market,
        "data_window": data_window,
        "started_at": empty_to_none(row["starttime"]),
        "ended_at": empty_to_none(row["stoptime"]),
        "start_station_id": empty_to_none(row["start station id"]),
        "end_station_id": empty_to_none(row["end station id"]),
        "start_station_name": empty_to_none(row["start station name"]),
        "end_station_name": empty_to_none(row["end station name"]),
        "start_lat": empty_to_none(row["start station latitude"]),
        "start_lng": empty_to_none(row["start station longitude"]),
        "end_lat": empty_to_none(row["end station latitude"]),
        "end_lng": empty_to_none(row["end station longitude"]),
    }


def get_reject_reason(row: dict) -> str | None:
    if not row["started_at"]:
        return "missing start time"

    if not row["ended_at"]:
        return "missing end time"

    if not row["start_station_id"]:
        return "never started at a station"

    if not row["end_station_id"]:
        return "never docked"

    return None


def transform_file(csv_file: Path, market: str, data_window: str,) -> tuple[list[dict], list[dict]]:

    valid_rows = []
    reject_rows = []

    with csv_file.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if "starttime" in row:
                conformed = conform_old(row, market, data_window)
            else:
                conformed = conform_new(row, market, data_window)

            reason = get_reject_reason(conformed)

            if reason is None:
                valid_rows.append(conformed)
            else:
                conformed["reason"] = reason
                reject_rows.append(conformed)

    return valid_rows, reject_rows