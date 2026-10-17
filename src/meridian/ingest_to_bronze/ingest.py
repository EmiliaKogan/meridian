import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
import json
from datetime import datetime, timezone
import httpx

from meridian.paths import data_window_dir

S3_URL = "https://s3.amazonaws.com/tripdata/"


def source_prefixes(market: str, data_window: str) -> list[str]:
    year, month = data_window.split("-")
    if market == "NYC":
        return [f"{year}{month}-", f"{year}-citibike-tripdata"]
    if market == "JC":
        return [f"JC-{year}{month}-"]
    raise ValueError(f"Unknown market: {market}")


def source_files(xml: str) -> list[tuple[str, str]]:
    files = []
    for content in xml.split("<Contents>")[1:]:
        key = content.split("<Key>", 1)[1].split("</Key>", 1)[0]
        if not key.lower().endswith(".zip"):
            continue
        modified = content.split("<LastModified>", 1)[1].split("</LastModified>", 1)[0]
        files.append((key, modified))
    return files


def find_source_zip(market: str, data_window: str) -> tuple[str, str]:
    for prefix in source_prefixes(market, data_window):
        response = httpx.get(S3_URL, params={"list-type": "2", "prefix": prefix})
        response.raise_for_status()
        files = source_files(response.text)
        if files:
            return max(files, key=lambda item: item[1])
    raise ValueError(f"No source ZIP found for {market} {data_window}")


def download_source_zip(source_zip: str) -> Path:
    temp_dir = Path("tmp")
    temp_dir.mkdir(exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".zip", dir=temp_dir, delete=False,
    )
    with temp_file:
        with httpx.stream("GET", S3_URL + source_zip) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
    return Path(temp_file.name)


def expected_csv_prefix(market: str, data_window: str) -> str:
    year, month = data_window.split("-")
    if market == "NYC":
        return f"{year}{month}"
    if market == "JC":
        return f"JC-{year}{month}"
    raise ValueError(f"Unknown market: {market}")


def find_latest_csvs_in_zip(
    zip_path: Path, market: str, data_window: str,
) -> list[str]:
    expected = expected_csv_prefix(market, data_window)
    groups = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            path = Path(info.filename)
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            if path.suffix.lower() != ".csv" or expected not in path.name:
                continue
            stem = re.sub(r"_\d+$", "", path.stem)
            groups.setdefault((str(path.parent), stem), []).append(info)
    if not groups:
        raise ValueError(f"No CSV found for {market} {data_window}")
    latest = max(groups.values(), key=lambda g: max(i.date_time for i in g))
    return [info.filename for info in sorted(latest, key=lambda i: i.filename)]


def save_csv_from_zip(
    zip_path: Path, csv_path: str, destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        data = archive.read(csv_path)
    destination.write_bytes(data)


def replace_window(staging: Path, window_dir: Path) -> None:
    backup = staging.parent / f"{staging.name}.backup"
    if window_dir.exists():
        os.replace(window_dir, backup)
    try:
        os.replace(staging, window_dir)
    except OSError:
        if backup.exists():
            os.replace(backup, window_dir)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def write_manifest(staging: Path, zip_path: Path, csv_paths: list[str], source_key: str, last_modified: str,) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            {
                "name": name,
                "timestamp": datetime(*archive.getinfo(name).date_time).isoformat(),
            }
            for name in csv_paths
        ]
    manifest = {
        "source_key": source_key,
        "last_modified": last_modified,
        "members": members,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2))



def save_bronze_csvs(zip_path: Path, csv_paths: list[str], market: str, data_window: str, source_key: str | None = None, last_modified: str | None = None,) -> None:
    if not source_key or not last_modified:
        raise ValueError("Source metadata required")
    window_dir = data_window_dir(market, data_window)
    window_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bronze-", dir=window_dir.parent))
    try:
        for csv_path in csv_paths:
            save_csv_from_zip(zip_path, csv_path, staging / Path(csv_path).name)
            write_manifest(staging, zip_path, csv_paths, source_key, last_modified)
        replace_window(staging, window_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

