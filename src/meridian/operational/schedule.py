import argparse

from meridian.operational.client import dag_id, request, token
from meridian.operational.config import MARKETS


def _validate(market: str, state: str) -> None:
    """Validate the schedule arguments."""
    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}")
    if state not in ("on", "off"):
        raise ValueError(f"Invalid schedule state: {state}")


def set_schedule(market: str, state: str) -> None:
    """Pause or unpause the monthly market DAG."""
    _validate(market, state)
    request(
        "PATCH",
        f"/api/v2/dags/{dag_id(market)}",
        {"is_paused": state == "off"},
        token(),
    )


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("market")
    parser.add_argument("state")
    return parser.parse_args(args)


def run_cli() -> None:
    args = parse_args()
    set_schedule(args.market, args.state)


if __name__ == "__main__":
    run_cli()