"""Shared helpers for the demo scripts. Standard library only, so the scripts run anywhere
Python 3.12+ is installed, without the virtual environment."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://localhost:8080"
REPO_ROOT = Path(__file__).resolve().parents[1]


def read_dotenv(name: str) -> str | None:
    """Return a value from the environment, falling back to the repo's .env file."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == name:
                    return value.strip()
    return None


def base_url(cli_value: str | None) -> str:
    return (cli_value or os.environ.get("ORDERS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def request(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30,
) -> tuple[int, dict | str, dict, float]:
    """Return (status, parsed_body, response_headers, elapsed_ms). Never raises on HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status, raw, resp_headers = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as err:
        status, raw, resp_headers = err.code, err.read(), err.headers
    elapsed_ms = (time.perf_counter() - started) * 1000
    resp_headers = {
        k.lower(): v for k, v in resp_headers.items()
    }  # header names are case-insensitive
    try:
        parsed: dict | str = json.loads(raw) if raw else {}
    except ValueError:
        parsed = raw.decode(errors="replace")
    return status, parsed, resp_headers, elapsed_ms
