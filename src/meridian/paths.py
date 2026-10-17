
import os
from pathlib import Path


def data_window_dir(market: str, data_window: str) -> Path:
    year, month = data_window.split("-")
    base_dir = Path(os.getenv("BRONZE_DIR", "/data/bronze"))
    return base_dir / market / year / month