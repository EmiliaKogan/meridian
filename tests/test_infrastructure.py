import subprocess


def test_just_up_succeeds():
    result = subprocess.run(
        ["just", "up"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_postgres_is_available(stack_is_running):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "meridian",
            "-d",
            "meridian",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_just_down_succeeds():
    result = subprocess.run(
        ["just", "down"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_just_down_stops_postgres(stack_is_running):
    result = subprocess.run(
        ["just", "down"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    result = subprocess.run(
        [
            "docker",
            "compose",
            "ps",
            "--services",
            "--filter",
            "status=running",
        ],
        capture_output=True,
        text=True,
    )

    assert "postgres" not in result.stdout