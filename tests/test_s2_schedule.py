import pytest

from meridian.operational.schedule import (
    parse_args,
    run_cli,
    set_schedule,
)


def test_schedule_on_unpauses_dag(monkeypatch):
    """Schedule on unpauses the market DAG."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.schedule.token",
        lambda: "TOKEN",
    )
    monkeypatch.setattr(
        "meridian.operational.schedule.request",
        lambda *args: calls.append(args),
    )

    set_schedule("jc", "on")

    assert calls == [
        (
            "PATCH",
            "/api/v2/dags/meridian_jc_monthly",
            {"is_paused": False},
            "TOKEN",
        )
    ]


def test_schedule_off_pauses_dag(monkeypatch):
    """Schedule off pauses the market DAG."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.schedule.token",
        lambda: "TOKEN",
    )
    monkeypatch.setattr(
        "meridian.operational.schedule.request",
        lambda *args: calls.append(args),
    )

    set_schedule("nyc", "off")

    assert calls == [
        (
            "PATCH",
            "/api/v2/dags/meridian_nyc_monthly",
            {"is_paused": True},
            "TOKEN",
        )
    ]


def test_schedule_rejects_unknown_market(monkeypatch):
    """An unknown market is rejected."""
    monkeypatch.setattr(
        "meridian.operational.schedule.token",
        lambda: "TOKEN",
    )

    with pytest.raises(ValueError, match="Unknown market"):
        set_schedule("bad", "on")


def test_schedule_rejects_invalid_state(monkeypatch):
    """Only on and off are accepted."""
    monkeypatch.setattr(
        "meridian.operational.schedule.token",
        lambda: "TOKEN",
    )

    with pytest.raises(ValueError, match="Invalid schedule state"):
        set_schedule("jc", "maybe")


def test_parse_args_reads_schedule_command():
    """CLI parser reads market and schedule state."""
    args = parse_args(["jc", "on"])

    assert args.market == "jc"
    assert args.state == "on"


def test_run_cli_passes_arguments(monkeypatch):
    """CLI arguments are passed to set_schedule."""
    calls = []

    monkeypatch.setattr(
        "meridian.operational.schedule.parse_args",
        lambda: parse_args(["jc", "off"]),
    )
    monkeypatch.setattr(
        "meridian.operational.schedule.set_schedule",
        lambda *args: calls.append(args),
    )

    run_cli()

    assert calls == [("jc", "off")]