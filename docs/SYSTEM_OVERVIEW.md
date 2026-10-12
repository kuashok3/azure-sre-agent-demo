# System Overview — Contoso Orders

> Audience: new team members **and** Azure SRE Agent. Plain language first, details in linked docs.
> Status legend: **[LIVE-LOCAL]** verified in docker compose · **[PLANNED-AZURE]** designed, not yet deployed (M4/M5).

## What the business does

Contoso Orders is a fictional online shop's **order service**. Customers (or other systems) call it to:

1. **Create an order**: a customer ID plus line items (SKU, quantity, unit price).
2. **Check out an order**: charge the order total through a payment service.
3. **Look up orders** and simple **business stats** (orders by status, paid revenue).

There is no web front end. The API is the product, and Swagger UI at `/docs` is the human interface.

## Critical user journeys

| Journey | Endpoint | What "working" means | Depends on |
|---|---|---|---|
| Create order | `POST /api/v1/orders` | 201, order stored with correct total | PostgreSQL |
| Checkout | `POST /api/v1/orders/{id}/checkout` | 200 PAID, or 402 if the payment is declined for business reasons | PostgreSQL + payment-stub |
| View order | `GET /api/v1/orders/{id}` | 200 with items | PostgreSQL |

## Components

| Component | What it is | Local [LIVE-LOCAL] | Azure [PLANNED-AZURE] |
|---|---|---|---|
| **orders-api** | Python FastAPI service, the system under test | container, host port 8080 | Container App `ca-orders-api`, public HTTPS |
| **payment-stub** | Fake payment processor. Approves ≤ 1,000,000 cents and declines above | container, host port 8081 | Container App `ca-payment-stub`, **internal only** |
| **PostgreSQL 16** | Stores orders and order items | container, host port 5434 | Azure Database for PostgreSQL Flexible Server (B1ms) |
| **migrate** | One-shot job applying `migrations/*.sql` | container that exits 0 | decided in M4 |
| **Telemetry** | Logs, traces, metrics | JSON to stdout only | Application Insights + Log Analytics |

Full picture: [ARCHITECTURE.md](ARCHITECTURE.md). Dependencies: [DEPENDENCIES.md](DEPENDENCIES.md).

## What "healthy" looks like

| Signal | Healthy value | Where |
|---|---|---|
| `GET /health/live` | 200 `{"status":"alive"}` | always, unless the process is dead |
| `GET /health/ready` | 200 `{"status":"ready"}` | 503 `not_ready` = database problem; 200 `degraded` = payment-stub problem |
| 5xx share of `/api/*` | 0% | logs `event=http_request`, AppRequests |
| Latency | Local baseline: p50 ≈ 15–30 ms when idle; p95 ≈ 200 ms at ~145 req/s (single worker) | `scripts/load.py`, AppRequests |
| Active faults | none | `python scripts/fault.py list` → `Active faults: none` |

Azure baseline numbers will be recorded in M6.

## Things that look like failures but are not

| Observation | Why it is normal |
|---|---|
| HTTP 402 `payment_declined` on checkout | Business rule: totals above $10,000 (1,000,000 cents) are declined |
| HTTP 404 `order_not_found` | Client asked for an order that does not exist |
| HTTP 409 `order_state_conflict` | Client tried to pay an already-paid order |
| HTTP 422 | Client sent invalid input |
| Readiness `degraded` (200) | payment-stub is down. Orders can still be created; only checkout fails |

## Controlled failures (demo only)

The service can be broken on purpose through a token-protected admin API. It is off by default.
See [KNOWN_FAILURE_MODES.md](KNOWN_FAILURE_MODES.md). **Synthetic faults announce themselves**:
error messages contain `injected fault`, and the logs contain `event=fault_enabled`. Real outages
(a database that has been stopped, a dependency that has been scaled to zero) do not.
