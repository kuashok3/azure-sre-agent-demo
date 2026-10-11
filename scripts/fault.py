"""Turn controlled failures on and off.

Usage:
    python scripts/fault.py list
    python scripts/fault.py enable latency --param delay_ms=1500
    python scripts/fault.py enable http_5xx --param error_rate=0.3
    python scripts/fault.py enable db_connection_failure
    python scripts/fault.py enable db_latency --param delay_ms=2500
    python scripts/fault.py enable payment_latency --param delay_ms=5000
    python scripts/fault.py enable payment_errors
    python scripts/fault.py disable latency
    python scripts/fault.py reset                     # recover: turn everything off

The token comes from --token, the FAULT_ADMIN_TOKEN environment variable, or the repo's .env file.
The target comes from --base-url, ORDERS_BASE_URL, or http://localhost:8080.
"""

import argparse
import json
import sys

from _common import base_url, read_dotenv, request


def parse_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--param must look like name=value, got {pair!r}")
        key, value = pair.split("=", 1)
        params[key] = float(value)
    return params


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Control demo failure injection", formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("action", choices=["list", "enable", "disable", "reset"])
    parser.add_argument("name", nargs="?", help="fault name (for enable/disable)")
    parser.add_argument("--param", action="append", default=[], help="name=value, repeatable")
    parser.add_argument("--base-url")
    parser.add_argument("--token")
    args = parser.parse_args()

    token = args.token or read_dotenv("FAULT_ADMIN_TOKEN")
    if not token:
        print("No token: pass --token or set FAULT_ADMIN_TOKEN", file=sys.stderr)
        return 2
    url = f"{base_url(args.base_url)}/admin/faults"
    headers = {"X-Fault-Token": token}

    if args.action in ("enable", "disable") and not args.name:
        parser.error(f"{args.action} needs a fault name (see: fault.py list)")

    if args.action == "list":
        status, body, _, _ = request("GET", url, headers=headers)
        if status == 200:
            print("Available faults:")
            for fault in body["available"]:
                params = ", ".join(f"{k}={v['default']}" for k, v in fault["params"].items())
                print(f"  {fault['name']:<22} {fault['description']}  [{params}]")
            print(
                "\nActive faults:",
                json.dumps(body["active"], indent=2) if body["active"] else "none",
            )
            return 0
    elif args.action == "enable":
        status, body, _, _ = request(
            "PUT", f"{url}/{args.name}", {"params": parse_params(args.param)}, headers
        )
    elif args.action == "disable":
        status, body, _, _ = request("DELETE", f"{url}/{args.name}", headers=headers)
    else:
        status, body, _, _ = request("DELETE", url, headers=headers)

    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
