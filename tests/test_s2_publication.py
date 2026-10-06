import pytest

from meridian.operational.publication import is_published


def test_existing_source_is_published(monkeypatch):
    monkeypatch.setattr(
        "meridian.operational.publication.find_source_zip",
        lambda market, month: "source.zip",
    )

    assert is_published("jc", "2026-06") is True


def test_missing_source_is_not_published(monkeypatch):
    def missing_source(market, month):
        raise ValueError(
            "No source ZIP found for JC 2026-09"
        )

    monkeypatch.setattr(
        "meridian.operational.publication.find_source_zip",
        missing_source,
    )

    assert is_published("jc", "2026-09") is False


def test_other_source_error_is_raised(monkeypatch):
    def invalid_market(market, month):
        raise ValueError("Unknown market: XX")

    monkeypatch.setattr(
        "meridian.operational.publication.find_source_zip",
        invalid_market,
    )

    with pytest.raises(
        ValueError,
        match="Unknown market",
    ):
        is_published("xx", "2026-09")