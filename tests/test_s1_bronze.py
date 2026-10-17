import json
import zipfile
from datetime import datetime

import pytest

from meridian.ingest_to_bronze.ingest import find_source_zip, save_bronze_csvs
from meridian.ingest_to_bronze.main import run
from meridian.parsing import parse_dataset_market


GOOD = {
    "job": "trips:jc",
    "market": "JC",
    "month": "2026-06",
    "source": "source.zip",
    "last_modified": "2026-07-01T00:00:00Z",
    "csv": "trips.csv",
}

SOURCE_METADATA = {
    "source_key": "JC-202606-citibike-tripdata.csv.zip",
    "last_modified": "2026-07-01T10:00:00Z",
}


@pytest.fixture
def bronze_mocks(monkeypatch, tmp_path):
    zip_path = tmp_path / GOOD["source"]
    zip_path.touch()
    calls = []

    def find_source(market, month):
        calls.append(("find", market, month))
        return GOOD["source"], GOOD["last_modified"]

    def download(source):
        calls.append(("download", source))
        return zip_path

    def find_csvs(path, market, month):
        calls.append(("csvs", path, market, month))
        return [GOOD["csv"]]

    def save(
        path, csvs, market, month, *, source_key, last_modified
    ):
        calls.append((
            "save", path, csvs, market, month,
            source_key, last_modified,
        ))

    prefix = "meridian.ingest_to_bronze.main."
    monkeypatch.setattr(prefix + "find_source_zip", find_source)
    monkeypatch.setattr(prefix + "download_source_zip", download)
    monkeypatch.setattr(
        prefix + "find_latest_csvs_in_zip", find_csvs
    )
    monkeypatch.setattr(prefix + "save_bronze_csvs", save)

    return zip_path, calls


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("trips:jc", ("trips", "JC")),
        ("trips:nyc", ("trips", "NYC")),
    ],
)
def test_parse_dataset_market(value, expected):
    assert parse_dataset_market(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("stations:jc", "Unknown dataset"),
        ("trips:unknown", "Unknown market"),
    ],
)
def test_invalid_dataset_or_market_fails(value, message):
    with pytest.raises(ValueError, match=message):
        parse_dataset_market(value)


@pytest.mark.parametrize(
    ("market", "key"),
    [
        ("JC", "JC-202207-citbike-tripdata.csv.zip"),
        ("NYC", "202207-citbike-tripdata.csv.zip"),
    ],
)
def test_find_source_zip_ignores_name_typo(
    monkeypatch, market, key
):
    last_modified = "2022-08-01T00:00:00Z"
    xml = (
        "<ListBucketResult><Contents>"
        f"<Key>{key}</Key>"
        f"<LastModified>{last_modified}</LastModified>"
        "</Contents></ListBucketResult>"
    )

    class Response:
        text = xml

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.ingest.httpx.get",
        lambda *args, **kwargs: Response(),
    )

    assert find_source_zip(market, "2022-07") == (
        key, last_modified
    )


def test_bronze_calls_existing_ingestion(bronze_mocks):
    zip_path, calls = bronze_mocks

    run(GOOD["job"], GOOD["month"])

    assert calls == [
        ("find", "JC", GOOD["month"]),
        ("download", GOOD["source"]),
        ("csvs", zip_path, "JC", GOOD["month"]),
        (
            "save",
            zip_path,
            [GOOD["csv"]],
            "JC",
            GOOD["month"],
            GOOD["source"],
            GOOD["last_modified"],
        ),
    ]


def test_bronze_removes_zip_after_success(bronze_mocks):
    zip_path, _ = bronze_mocks

    run(GOOD["job"], GOOD["month"])

    assert not zip_path.exists()


def test_bronze_removes_zip_after_failure(
    bronze_mocks, monkeypatch
):
    zip_path, _ = bronze_mocks

    def fail_save(*args, **kwargs):
        raise RuntimeError("Save failed")

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.save_bronze_csvs",
        fail_save,
    )

    with pytest.raises(RuntimeError, match="Save failed"):
        run(GOOD["job"], GOOD["month"])

    assert not zip_path.exists()


def make_zip(path, **members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_bronze_uses_configured_directory(
    tmp_path, monkeypatch
):
    bronze_root = tmp_path / "bronze"
    monkeypatch.setenv("BRONZE_DIR", str(bronze_root))

    source = tmp_path / "source.zip"
    make_zip(source, **{"trips.csv": "ride_id\n123\n"})

    save_bronze_csvs(
        source,
        ["trips.csv"],
        "JC",
        "2026-06",
        **SOURCE_METADATA,
    )

    saved = bronze_root / "JC" / "2026" / "06" / "trips.csv"
    assert saved.read_text() == "ride_id\n123\n"


def test_reingest_removes_old_csvs(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BRONZE_DIR", str(tmp_path / "bronze")
    )

    source = tmp_path / "source.zip"
    make_zip(source, **{"new.csv": "ride_id\n123\n"})

    window = tmp_path / "bronze" / "JC" / "2026" / "06"
    window.mkdir(parents=True)
    (window / "old.csv").write_text("ride_id\n999\n")

    save_bronze_csvs(
        source,
        ["new.csv"],
        "JC",
        "2026-06",
        **SOURCE_METADATA,
    )

    assert sorted(
        p.name for p in window.glob("*.csv")
    ) == ["new.csv"]
    assert (
        window / "new.csv"
    ).read_text() == "ride_id\n123\n"


def test_reingest_failure_preserves_old_window(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "BRONZE_DIR", str(tmp_path / "bronze")
    )

    window = tmp_path / "bronze" / "JC" / "2026" / "06"
    window.mkdir(parents=True)
    (window / "old.csv").write_text("ride_id\n999\n")

    source = tmp_path / "source.zip"
    make_zip(source, **{"new.csv": "ride_id\n123\n"})

    def fail_write(*args):
        raise OSError("Simulated write failure")

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.ingest.save_csv_from_zip",
        fail_write,
    )

    with pytest.raises(
        OSError, match="Simulated write failure"
    ):
        save_bronze_csvs(
            source,
            ["new.csv"],
            "JC",
            "2026-06",
            **SOURCE_METADATA,
        )

    assert (
        window / "old.csv"
    ).read_text() == "ride_id\n999\n"
    assert sorted(
        p.name for p in window.glob("*.csv")
    ) == ["old.csv"]


def test_reingest_partial_write_preserves_old_window(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "BRONZE_DIR", str(tmp_path / "bronze")
    )

    window = tmp_path / "bronze" / "JC" / "2026" / "06"
    window.mkdir(parents=True)
    (window / "old.csv").write_text("old data")

    source = tmp_path / "source.zip"
    make_zip(
        source,
        **{
            "first.csv": "first data",
            "second.csv": "second data",
        },
    )

    from meridian.ingest_to_bronze import ingest

    original = ingest.save_csv_from_zip
    calls = 0

    def fail_second(zip_path, csv_path, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Second CSV failed")
        original(zip_path, csv_path, destination)

    monkeypatch.setattr(
        ingest, "save_csv_from_zip", fail_second
    )

    with pytest.raises(
        OSError, match="Second CSV failed"
    ):
        save_bronze_csvs(
            source,
            ["first.csv", "second.csv"],
            "JC",
            "2026-06",
            **SOURCE_METADATA,
        )

    assert sorted(
        p.name for p in window.iterdir()
    ) == ["old.csv"]
    assert (
        window / "old.csv"
    ).read_text() == "old data"
    assert sorted(
        p.name for p in window.parent.iterdir()
    ) == ["06"]


def test_bronze_writes_source_manifest(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "BRONZE_DIR", str(tmp_path / "bronze")
    )

    source = tmp_path / "source.zip"

    with zipfile.ZipFile(source, "w") as archive:
        member = zipfile.ZipInfo("trips.csv")
        member.date_time = (2026, 6, 30, 12, 0, 0)
        archive.writestr(member, "ride_id\n123\n")

    save_bronze_csvs(
        source,
        ["trips.csv"],
        "JC",
        "2026-06",
        **SOURCE_METADATA,
    )

    window = tmp_path / "bronze" / "JC" / "2026" / "06"
    manifest = json.loads(
        (window / "manifest.json").read_text()
    )

    assert (
        manifest["source_key"]
        == SOURCE_METADATA["source_key"]
    )
    assert (
        manifest["last_modified"]
        == SOURCE_METADATA["last_modified"]
    )
    assert manifest["members"] == [
        {
            "name": "trips.csv",
            "timestamp": "2026-06-30T12:00:00",
        },
    ]
    assert datetime.fromisoformat(
        manifest["fetched_at"]
    )
    assert (
        window / "trips.csv"
    ).read_text() == "ride_id\n123\n"


def test_bronze_requires_source_metadata(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "BRONZE_DIR", str(tmp_path / "bronze")
    )

    source = tmp_path / "source.zip"
    make_zip(source, **{"trips.csv": "ride_id\n123\n"})

    with pytest.raises(
        ValueError, match="Source metadata required"
    ):
        save_bronze_csvs(
            source,
            ["trips.csv"],
            "JC",
            "2026-06",
        )

    window = tmp_path / "bronze" / "JC" / "2026" / "06"
    assert not window.exists()


def test_replace_window_restores_backup_on_failure(
    tmp_path, monkeypatch
):
    from meridian.ingest_to_bronze import ingest

    old = tmp_path / "06"
    old.mkdir()
    (old / "old.csv").write_text("old data")

    staging = tmp_path / ".bronze-test"
    staging.mkdir()
    (staging / "new.csv").write_text("new data")

    original_replace = ingest.os.replace

    def fail_publish(src, dst):
        if src == staging and dst == old:
            raise OSError("Publish failed")
        return original_replace(src, dst)

    monkeypatch.setattr(
        ingest.os, "replace", fail_publish
    )

    with pytest.raises(OSError, match="Publish failed"):
        ingest.replace_window(staging, old)

    assert (
        old / "old.csv"
    ).read_text() == "old data"
    assert not (old / "new.csv").exists()
    assert not (
        tmp_path / ".bronze-test.backup"
    ).exists()
