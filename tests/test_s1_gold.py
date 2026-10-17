
import json
import subprocess

GOOD = {
    "market": "jc",
    "station": "JC115",
    "day": "2026-06-02",
    "departures": 216,
    "arrivals": 209,
}


def test_gold_jc115_regression():
    """Gold must preserve the expected station-day counts."""
    result = subprocess.run(
        [
            "just", "report", "daily-station-trips",
            GOOD["market"], GOOD["station"], GOOD["day"],
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout.splitlines()[-1])
    assert actual == GOOD
