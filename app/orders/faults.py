"""The failure scenarios orders-api supports. All are off by default.

| name                  | effect                                         | HTTP result     |
|-----------------------|------------------------------------------------|-----------------|
| latency               | sleep before handling /api/* requests          | slow 2xx        |
| http_5xx              | unhandled exception in /api/* requests         | 500             |
| db_connection_failure | DB calls fail as if PostgreSQL were down       | 503 + not ready |
| db_latency            | sleep inside every DB call (slow dependency)   | slow 2xx        |
| payment_latency       | forwarded: payment-stub slow -> client timeout | 504 on checkout |
| payment_errors        | forwarded: payment-stub returns 503            | 503 on checkout |

Traffic spikes are generated externally with scripts/load.py. Recovery = DELETE /admin/faults.
"""

from app.common.faults import FaultSpec, delay_param, rate_param

ORDERS_FAULTS: dict[str, FaultSpec] = {
    "latency": FaultSpec(
        "latency",
        "Add delay to every /api/* request handled by orders-api",
        "orders-api /api/*",
        {"delay_ms": delay_param(1500), "probability": rate_param(1.0, "Share of requests")},
    ),
    "http_5xx": FaultSpec(
        "http_5xx",
        "Fail a share of /api/* requests with an unhandled exception (HTTP 500)",
        "orders-api /api/*",
        {"error_rate": rate_param(0.5, "Share of requests that fail")},
    ),
    "db_connection_failure": FaultSpec(
        "db_connection_failure",
        "Make database calls fail as if PostgreSQL were unreachable",
        "orders-api -> PostgreSQL",
        {"probability": rate_param(1.0, "Share of DB calls that fail")},
    ),
    "db_latency": FaultSpec(
        "db_latency",
        "Add delay inside every database call",
        "orders-api -> PostgreSQL",
        {"delay_ms": delay_param(2000), "probability": rate_param(1.0, "Share of DB calls")},
    ),
    "payment_latency": FaultSpec(
        "payment_latency",
        "Make payment-stub slow so checkout exceeds PAYMENT_TIMEOUT_SECONDS",
        "payment-stub (forwarded)",
        {"delay_ms": delay_param(5000)},
    ),
    "payment_errors": FaultSpec(
        "payment_errors",
        "Make payment-stub return HTTP 503 for a share of payments",
        "payment-stub (forwarded)",
        {"error_rate": rate_param(1.0, "Share of payments that fail")},
    ),
}

# orders-api fault name -> payment-stub fault name
FORWARDED_FAULTS = {"payment_latency": "latency", "payment_errors": "errors"}
