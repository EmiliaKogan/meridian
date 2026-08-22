import sys
import httpx
from pathlib import Path
import tempfile
import zipfile
import io, os, re
import csv
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

S3_URL = "https://s3.amazonaws.com/tripdata/"


def find_source_zip(market: str, data_window: str) -> str:
    year, month = data_window.split("-")

    if market == "NYC":
        prefixes = [
            f"{year}{month}-citibike-tripdata",
            f"{year}-citibike-tripdata",]
    elif market == "JC":
        prefixes = [f"JC-{year}{month}-citibike-tripdata",]
    else:
        raise ValueError(f"Unknown market: {market}")

    for prefix in prefixes:
        response = httpx.get(S3_URL, params={"list-type": "2","prefix": prefix,},)
        response.raise_for_status()

        keys = [part.split("</Key>", 1)[0] for part in response.text.split("<Key>")[1:]]

        if keys:
            if len(keys) > 1:
                raise ValueError(f"Multiple source files found for "f"{market} {data_window}: {keys}")
            return keys[0]

    raise ValueError(f"No source ZIP found for {market} {data_window}")


def download_source_zip(source_zip: str) -> Path:
    url = S3_URL + source_zip

    temp_dir = Path("tmp")
    temp_dir.mkdir(exist_ok=True)

    temp_file = tempfile.NamedTemporaryFile(suffix=".zip", dir=temp_dir, delete=False,)

    with temp_file:
        with httpx.stream("GET", url) as response:
            response.raise_for_status()

            for chunk in response.iter_bytes():
                temp_file.write(chunk)

    return Path(temp_file.name)


def find_latest_csvs_in_zip(zip_path: Path, market: str, data_window: str,) -> list[str]:

    year, month = data_window.split("-")

    if market == "NYC":
        expected = f"{year}{month}"
    elif market == "JC":
        expected = f"JC-{year}{month}"
    else:
        raise ValueError(f"Unknown market: {market}")

    groups = {}

    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue

            path = Path(info.filename)

            if path.suffix.lower() != ".csv":
                continue

            if expected not in path.name:
                continue

            stem = re.sub(r"_\d+$", "", path.stem)
            key = (str(path.parent), stem)

            groups.setdefault(key, []).append(info)

    if not groups:
        raise ValueError(
            f"No CSV found for {market} {data_window}"
        )

    latest_group = max(groups.values(), key=lambda group: max(info.date_time for info in group),)

    return [info.filename for info in sorted(latest_group, key=lambda info: info.filename)]


def save_csv_from_zip(zip_path: Path,csv_path: str,destination: Path,) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        data = z.read(csv_path)

    destination.write_bytes(data)


def save_bronze_csvs(zip_path: Path, csv_paths: list[str], market: str, data_window: str,) -> None:
    year, month = data_window.split("-")
    bronze_dir = Path("/data/bronze") / market / year / month

    for csv_path in csv_paths:
        destination = bronze_dir / Path(csv_path).name
        save_csv_from_zip(zip_path, csv_path, destination)   


##############################################################

def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()

    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def main() -> None:
    """Run the Bronze ingestion job."""

    dataset, market = parse_dataset_market(sys.argv[1])
    data_window = sys.argv[2]

    print(f"Bronze ingestion started")
    print(f"Market: {market}")
    print(f"Window: {data_window}")

    source_zip = find_source_zip(market, data_window)
    print(f"Source ZIP: {source_zip}")

    zip_path = download_source_zip(source_zip)

    try:
        csv_paths = find_latest_csvs_in_zip(zip_path, market, data_window,)

        # for csv_path in csv_paths:
        #     print(f"Latest CSV: {csv_path}")

        save_bronze_csvs(zip_path, csv_paths, market, data_window,)
        print("Bronze ingestion completed")

    finally:
        zip_path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()


# def read_csv_from_zip(zip_path: Path, csv_name: str):
#     with zipfile.ZipFile(zip_path) as z:
#         with z.open(csv_name) as csv_file:
#             text_file = io.TextIOWrapper(csv_file,encoding="utf-8-sig",)
#             reader = csv.DictReader(text_file)

#             for row in reader:
#                 yield row

# def make_bronze_row(
#     row: dict,
#     market: str,
#     data_window: str,
# ) -> dict:
#     return {
#         "market": market,
#         "data_window": data_window,
#         "raw_data": json.dumps(row),
#         "source_system": "citibike-s3",
#         "read_at": datetime.now(timezone.utc),
#         "schema_version": "1",
#         "source_freshness": "source",
#     }

# def insert_bronze_batch(connection, batch: list[dict]) -> None:
#     connection.execute(
#         text("""
#             INSERT INTO bronze_trips (
#                 market, data_window, raw_data,
#                 source_system, read_at,
#                 schema_version, source_freshness
#             )
#             VALUES (
#                 :market, :data_window, :raw_data,
#                 :source_system, :read_at,
#                 :schema_version, :source_freshness
#             )
#         """),
#         batch,
#     )


# def load_to_bronze(
#     rows,
#     market: str,
#     data_window: str,
#     batch_size: int = 1000,
# ) -> None:
#     engine = create_engine(os.environ["DATABASE_URL"])
#     batch = []

#     with engine.begin() as connection:
#         for row in rows:
#             batch.append(make_bronze_row(row, market, data_window))

#             if len(batch) >= batch_size:
#                 insert_bronze_batch(connection, batch)
#                 batch.clear()

#         if batch:
#             insert_bronze_batch(connection, batch)
                