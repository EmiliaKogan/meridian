from meridian.operational.progress import progress


def select_month(conn, job: str) -> str | None:
    """Select the next month to process."""
    return progress(conn, job)["next"]