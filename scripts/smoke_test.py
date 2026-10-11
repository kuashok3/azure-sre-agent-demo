"""Smoke test: exercise every public endpoint once and check the documented status codes.

Usage:
    python scripts/smoke_test.py                       # local docker compose (http://localhost:8080)
    python scripts/smoke_test.py --base-url https://<your-app>.azurecontainerapps.io
Exit code 0 = all checks passed, 1 = at least one failed.
"""

import argparse
import sys
import uuid

from _common import base_url, request

ORDER = {
    "customer_id": "smoke-test",
    "currency": "USD",
    "items": [{"sku": "SMOKE-1", "quantity": 2, "unit_price_cents": 1500}],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url")
    args = parser.parse_args()
    url = base_url(args.base_url)
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

    print(f"Smoke testing {url}\n")
    status, body, _, _ = request("GET", f"{url}/")
    check(
        "GET / returns service description", status == 200 and body.get("service") == "orders-api"
    )

    status, body, _, _ = request("GET", f"{url}/health/live")
    check("GET /health/live is 200", status == 200, f"status={status}")

    status, body, _, _ = request("GET", f"{url}/health/ready")
    check(
        "GET /health/ready is 200 and ready",
        status == 200 and body.get("status") == "ready",
        f"status={status} body={body}",
    )

    status, body, _, _ = request("GET", f"{url}/info")
    check("GET /info reports a version", status == 200 and bool(body.get("version")), str(body))

    status, order, headers, elapsed = request("POST", f"{url}/api/v1/orders", ORDER)
    check(
        "POST /api/v1/orders creates order (201)",
        status == 201 and order.get("total_cents") == 3000,
        f"status={status} {elapsed:.0f}ms",
    )
    check("Response carries X-Correlation-ID", "x-correlation-id" in headers)
    order_id = order.get("id") if isinstance(order, dict) else None

    if order_id:
        status, body, _, _ = request("GET", f"{url}/api/v1/orders/{order_id}")
        check("GET /api/v1/orders/{id} is 200", status == 200, f"status={status}")

        status, body, _, elapsed = request("POST", f"{url}/api/v1/orders/{order_id}/checkout")
        check(
            "POST checkout pays the order (200, PAID)",
            status == 200 and body.get("status") == "PAID",
            f"status={status} {elapsed:.0f}ms",
        )
        status, body, _, _ = request("POST", f"{url}/api/v1/orders/{order_id}/checkout")
        check("Second checkout is rejected (409)", status == 409, f"status={status}")

    status, body, _, _ = request("GET", f"{url}/api/v1/orders?limit=5")
    check("GET /api/v1/orders lists orders", status == 200 and body.get("count", 0) >= 1)

    status, body, _, _ = request("GET", f"{url}/api/v1/orders/{uuid.uuid4()}")
    check(
        "Unknown order returns 404 with error body",
        status == 404 and body.get("error") == "order_not_found",
    )

    status, body, _, _ = request("GET", f"{url}/api/v1/stats")
    check("GET /api/v1/stats is 200", status == 200 and "total_orders" in body)

    status, body, _, _ = request("GET", f"{url}/admin/faults")
    check(
        "Fault admin API refuses calls without token (401 or 404)",
        status in (401, 404),
        f"status={status}",
    )

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
