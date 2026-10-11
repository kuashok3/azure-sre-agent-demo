"""Trigger every controlled failure, check its symptom, then check that recovery works.

Usage:
    python scripts/validate_faults.py                    # synthetic faults via /admin/faults
    python scripts/validate_faults.py --include-docker   # + REAL outages (local docker only)

Each scenario prints PASS/FAIL for "symptom observed" and "recovered after reset".
"""

import argparse
import subprocess
import sys
import time

from _common import base_url, read_dotenv, request

ORDER = {
    "customer_id": "fault-check",
    "items": [{"sku": "F-1", "quantity": 1, "unit_price_cents": 500}],
}


class Runner:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.headers = {"X-Fault-Token": token}
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str) -> None:
        self.failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({detail})")

    def fault(self, method: str, name: str = "", params: dict | None = None) -> None:
        path = f"{self.url}/admin/faults" + (f"/{name}" if name else "")
        status, body, _, _ = request(
            method, path, {"params": params or {}} if method == "PUT" else None, self.headers
        )
        if status != 200:
            raise SystemExit(f"Fault API call failed: {method} {path} -> {status} {body}")

    def new_order(self) -> str:
        status, body, _, _ = request("POST", f"{self.url}/api/v1/orders", ORDER)
        if status != 201:
            raise SystemExit(f"Could not create order for checkout test: {status} {body}")
        return body["id"]

    def healthy(self) -> tuple[bool, str]:
        ready, body, _, _ = request("GET", f"{self.url}/health/ready")
        api, _, _, ms = request("GET", f"{self.url}/api/v1/orders?limit=1")
        state = body.get("status") if isinstance(body, dict) else body
        return ready == 200 and state == "ready" and api == 200 and ms < 1000, (
            f"ready={ready}/{state} api={api} {ms:.0f}ms"
        )

    def wait_healthy(self, seconds: int = 30) -> tuple[bool, str]:
        deadline = time.monotonic() + seconds
        while True:
            ok, detail = self.healthy()
            if ok or time.monotonic() > deadline:
                return ok, detail
            time.sleep(1)


def docker(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], check=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--include-docker", action="store_true")
    args = parser.parse_args()
    token = read_dotenv("FAULT_ADMIN_TOKEN")
    if not token:
        print("FAULT_ADMIN_TOKEN not found (env or .env)", file=sys.stderr)
        return 2
    r = Runner(base_url(args.base_url), token)
    u = r.url

    print("Baseline")
    r.fault("DELETE")
    r.check("service healthy before tests", *r.wait_healthy())

    print("\n1. latency (1500 ms on /api/*)")
    r.fault("PUT", "latency", {"delay_ms": 1500})
    status, _, _, ms = request("GET", f"{u}/api/v1/orders?limit=1")
    r.check("API request slowed", status == 200 and ms >= 1500 * 0.9, f"{status} {ms:.0f}ms")
    _, _, _, ms = request("GET", f"{u}/health/live")
    r.check("health endpoint not slowed", ms < 500, f"{ms:.0f}ms")
    r.fault("DELETE")
    r.check("recovered", *r.wait_healthy())

    print("\n2. http_5xx (error_rate=1.0)")
    r.fault("PUT", "http_5xx", {"error_rate": 1.0})
    status, body, _, _ = request("GET", f"{u}/api/v1/orders?limit=1")
    r.check(
        "API returns 500 internal_error",
        status == 500 and body.get("error") == "internal_error",
        f"{status}",
    )
    r.fault("DELETE")
    r.check("recovered", *r.wait_healthy())

    print("\n3. db_connection_failure")
    r.fault("PUT", "db_connection_failure")
    status, body, _, _ = request("POST", f"{u}/api/v1/orders", ORDER)
    r.check(
        "create returns 503 database_unavailable",
        status == 503 and body.get("error") == "database_unavailable",
        f"{status}",
    )
    status, body, _, _ = request("GET", f"{u}/health/ready")
    r.check("readiness 503 not_ready", status == 503, f"{status} {body.get('status')}")
    r.fault("DELETE")
    r.check("recovered", *r.wait_healthy())

    print("\n4. db_latency (2000 ms per DB call)")
    r.fault("PUT", "db_latency", {"delay_ms": 2000})
    status, _, _, ms = request("GET", f"{u}/api/v1/stats")
    r.check("DB-backed request slowed", status == 200 and ms >= 2000 * 0.9, f"{status} {ms:.0f}ms")
    r.fault("DELETE")
    r.check("recovered", *r.wait_healthy())

    print("\n5. payment_latency (payment-stub 5000 ms > client timeout)")
    order_id = r.new_order()
    r.fault("PUT", "payment_latency", {"delay_ms": 5000})
    status, body, _, ms = request("POST", f"{u}/api/v1/orders/{order_id}/checkout")
    r.check("checkout returns 504 payment_service_timeout", status == 504, f"{status} {ms:.0f}ms")
    status, body, _, _ = request("GET", f"{u}/api/v1/orders/{order_id}")
    r.check(
        "order still PENDING (safe to retry)", body.get("status") == "PENDING", body.get("status")
    )
    r.fault("DELETE")
    status, body, _, _ = request("POST", f"{u}/api/v1/orders/{order_id}/checkout")
    r.check(
        "retry after recovery succeeds", status == 200 and body.get("status") == "PAID", f"{status}"
    )

    print("\n6. payment_errors (payment-stub returns 503)")
    order_id = r.new_order()
    r.fault("PUT", "payment_errors", {"error_rate": 1.0})
    status, body, _, _ = request("POST", f"{u}/api/v1/orders/{order_id}/checkout")
    r.check(
        "checkout returns 503 payment_service_unavailable",
        status == 503,
        f"{status} {body.get('error')}",
    )
    r.fault("DELETE")
    r.check("recovered", *r.wait_healthy())

    print("\n7. business decline is NOT an outage")
    big = {
        "customer_id": "big-spender",
        "items": [{"sku": "YACHT", "quantity": 1, "unit_price_cents": 2_000_000}],
    }
    status, body, _, _ = request("POST", f"{u}/api/v1/orders", big)
    status, body, _, _ = request("POST", f"{u}/api/v1/orders/{body['id']}/checkout")
    r.check("checkout over limit returns 402 payment_declined", status == 402, f"{status}")

    if args.include_docker:
        print("\n8. REAL outage: stop PostgreSQL container")
        docker("stop", "postgres")
        status, body, _, _ = request("POST", f"{u}/api/v1/orders", ORDER, timeout=20)
        r.check(
            "create returns 503 database_unavailable",
            status == 503,
            f"{status} {body.get('error')}",
        )
        docker("start", "postgres")
        r.check("recovered after PostgreSQL restart", *r.wait_healthy(60))

        print("\n9. REAL outage: stop payment-stub container")
        order_id = r.new_order()
        docker("stop", "payment-stub")
        status, body, _, _ = request("GET", f"{u}/health/ready")
        r.check(
            "readiness 200 but degraded",
            status == 200 and body.get("status") == "degraded",
            f"{status} {body.get('status')}",
        )
        status, body, _, _ = request("POST", f"{u}/api/v1/orders/{order_id}/checkout")
        r.check("checkout returns 503", status == 503, f"{status} {body.get('error')}")
        docker("start", "payment-stub")
        r.check("recovered after payment-stub restart", *r.wait_healthy(60))

    print(f"\n{'ALL SCENARIOS PASSED' if r.failures == 0 else f'{r.failures} CHECK(S) FAILED'}")
    return 0 if r.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
