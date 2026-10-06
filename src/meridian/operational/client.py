import json
import os
import urllib.error
import urllib.request


def base_url() -> str:
    """Return the Airflow API base URL."""
    return os.environ.get("AIRFLOW_BASE_URL", "http://airflow:8080")


def request(method: str, path: str, body=None, token=None):
    """Send a request to the Airflow API."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base_url() + path, data=data, method=method
    )
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        message = error.read().decode()
        raise RuntimeError(
            f"Airflow API error {error.code}: {message}"
        ) from error
    return json.loads(raw) if raw else None


def token() -> str:
    """Authenticate with Airflow and return an API token."""
    body = {
        "username": os.environ.get("AIRFLOW_USERNAME", "airflow"),
        "password": os.environ.get("AIRFLOW_PASSWORD", "airflow"),
    }
    return request("POST", "/auth/token", body)["access_token"]


def dag_id(market: str) -> str:
    """Return the monthly DAG ID for a market."""
    return f"meridian_{market}_monthly"