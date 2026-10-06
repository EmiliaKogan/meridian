import pytest

from meridian.ingest_to_bronze.main import main, parse_dataset_market
from meridian.ingest_to_bronze.ingest import find_source_zip


GOOD = {
    "job": "trips:jc",
    "market": "JC",
    "month": "2026-06",
}


def test_parse_dataset_market():
    dataset, market = parse_dataset_market(GOOD["job"])

    assert dataset == "trips"
    assert market == GOOD["market"]


def test_unknown_dataset_fails():
    with pytest.raises(
        ValueError,
        match="Unknown dataset",
    ):
        parse_dataset_market("stations:jc")


def test_unknown_market_fails():
    with pytest.raises(
        ValueError,
        match="Unknown market",
    ):
        parse_dataset_market("trips:unknown")

def test_find_source_zip_jc_ignores_name_typo(monkeypatch):
    xml = """
    <ListBucketResult>
        <Contents>
            <Key>JC-202207-citbike-tripdata.csv.zip</Key>
            <LastModified>2022-08-01T00:00:00Z</LastModified>
        </Contents>
    </ListBucketResult>
    """

    class Response:
        text = xml

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.ingest.httpx.get",
        lambda *args, **kwargs: Response(),
    )

    result = find_source_zip("JC", "2022-07")

    assert result == "JC-202207-citbike-tripdata.csv.zip"


def test_find_source_zip_nyc_ignores_name_typo(monkeypatch):
    xml = """
    <ListBucketResult>
        <Contents>
            <Key>202207-citbike-tripdata.csv.zip</Key>
            <LastModified>2022-08-01T00:00:00Z</LastModified>
        </Contents>
    </ListBucketResult>
    """

    class Response:
        text = xml

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.ingest.httpx.get",
        lambda *args, **kwargs: Response(),
    )

    result = find_source_zip("NYC", "2022-07")

    assert result == "202207-citbike-tripdata.csv.zip"

def test_bronze_calls_existing_ingestion(
    monkeypatch,
    tmp_path,
):
    zip_path = tmp_path / "source.zip"
    zip_path.touch()
    calls = []

    def find_source(market, month):
        calls.append(("find", market, month))
        return "source.zip"

    def download(source):
        calls.append(("download", source))
        return zip_path

    def find_csvs(path, market, month):
        calls.append(("csvs", path, market, month))
        return ["trips.csv"]

    def save(path, csvs, market, month):
        calls.append(
            ("save", path, csvs, market, month)
        )

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_source_zip",
        find_source,
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.download_source_zip",
        download,
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_latest_csvs_in_zip",
        find_csvs,
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.save_bronze_csvs",
        save,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["main", GOOD["job"], GOOD["month"]],
    )

    main()

    assert calls == [
        ("find", "JC", "2026-06"),
        ("download", "source.zip"),
        ("csvs", zip_path, "JC", "2026-06"),
        (
            "save",
            zip_path,
            ["trips.csv"],
            "JC",
            "2026-06",
        ),
    ]


def test_bronze_removes_zip_after_success(
    monkeypatch,
    tmp_path,
):
    zip_path = tmp_path / "source.zip"
    zip_path.touch()

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_source_zip",
        lambda market, month: "source.zip",
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.download_source_zip",
        lambda source: zip_path,
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_latest_csvs_in_zip",
        lambda path, market, month: ["trips.csv"],
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.save_bronze_csvs",
        lambda path, csvs, market, month: None,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["main", GOOD["job"], GOOD["month"]],
    )

    main()

    assert not zip_path.exists()


def test_bronze_removes_zip_after_failure(
    monkeypatch,
    tmp_path,
):
    zip_path = tmp_path / "source.zip"
    zip_path.touch()

    def fail_save(path, csvs, market, month):
        raise RuntimeError("Save failed")

    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_source_zip",
        lambda market, month: "source.zip",
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.download_source_zip",
        lambda source: zip_path,
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.find_latest_csvs_in_zip",
        lambda path, market, month: ["trips.csv"],
    )
    monkeypatch.setattr(
        "meridian.ingest_to_bronze.main.save_bronze_csvs",
        fail_save,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["main", GOOD["job"], GOOD["month"]],
    )

    with pytest.raises(
        RuntimeError,
        match="Save failed",
    ):
        main()

    assert not zip_path.exists()