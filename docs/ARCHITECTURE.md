# Architecture

> **[LIVE-LOCAL]** = verified in docker compose. **[PLANNED-AZURE]** = designed, built in M4/M5.

## 1. Logical view

```
                      X-Correlation-ID / W3C traceparent propagated on every hop
 client ──HTTPS──► orders-api ──HTTP (connect 1 s, read 2 s)──► payment-stub
                       │
                       └──SQL over TLS (connect 3 s, statement 5 s)──► PostgreSQL 16
                       │
                       └──OpenTelemetry (if connection string set)──► Application Insights ─► Log Analytics
```

## 2. Local deployment [LIVE-LOCAL]

`docker-compose.yml`, project name `sre-demo`:

| Service | Image | Host port → container | Notes |
|---|---|---|---|
| postgres | `postgres:16-alpine` | 5434 → 5432 | volume `pgdata`, healthcheck `pg_isready` |
| migrate | `sre-demo-app:local` | — | `python -m app.orders.migrate`, must exit 0 before orders-api starts |
| payment-stub | `sre-demo-app:local` | 8081 → 8001 | `python -m app.payment_stub` |
| orders-api | `sre-demo-app:local` (built here) | 8080 → 8000 | `python -m app.orders` |

## 3. Azure deployment [PLANNED-AZURE]

```
rg-sredemo-app (East US 2)
 ├─ Container Apps environment cae-sredemo  ── platform logs ─► log-sredemo
 │    ├─ ca-orders-api    external ingress :8000, identity id-orders-api
 │    └─ ca-payment-stub  internal ingress :8001
 ├─ Azure Database for PostgreSQL Flexible Server psql-sredemo-<suffix> (B1ms, Entra auth)
 ├─ Container Registry crsredemo<suffix> (Basic)       ◄─ AcrPull: id-orders-api
 ├─ Key Vault kv-sredemo-<suffix> (FAULT_ADMIN_TOKEN)  ◄─ Secrets User: id-orders-api
 ├─ Log Analytics log-sredemo + Application Insights appi-sredemo (workspace-based)
 └─ Action group + alert rules
rg-sredemo-agent
 └─ Azure SRE Agent (Reader on rg-sredemo-app)
```

Exact names, SKUs and identities are confirmed in M4 and recorded in [RESOURCE_INVENTORY.md](RESOURCE_INVENTORY.md).

## 4. Request flows

### Create order
1. Middleware assigns a correlation ID and starts a timer.
2. Fault dependency on `/api/*`: optional `latency` sleep, optional `http_5xx` exception.
3. `OrderService.create` → `ObservedRepository.create_order` opens a `postgresql create_order`
   CLIENT span (→ AppDependencies). DB faults are applied here.
4. Insert order and items in one transaction. Response 201.
5. Metrics `orders_created` and `order_value_cents` are recorded, plus a log line `event=order_created`.

### Checkout
1. Load order (404 if missing; 409 if already PAID).
2. `PaymentClient.charge` → `POST payment-stub /api/v1/payments` (HTTP dependency span).
   - 200 → mark PAID (conditional update `status <> 'PAID'` prevents double payment).
   - 402 → mark PAYMENT_FAILED, return 402.
   - read timeout → 504 `payment_service_timeout`. **The order stays PENDING** (safe to retry).
   - connection error or 5xx → 503 `payment_service_unavailable`. The order stays PENDING.

## 5. Code map

| Path | Responsibility |
|---|---|
| `app/common/` | Shared: settings, JSON logging, telemetry, correlation IDs, error model, fault registry, fault admin API, healthcheck |
| `app/orders/main.py` | App factory: wires settings, repository, payment client, routes, fault API |
| `app/orders/routes.py` | Health + `/api/v1` endpoints, request-level faults |
| `app/orders/service.py` | Business logic (create, checkout) and business metrics |
| `app/orders/repository.py` | SQL (`PostgresOrderRepository`) + telemetry/faults/error mapping (`ObservedRepository`) |
| `app/orders/payment_client.py` | HTTP client to payment-stub, timeout and error mapping |
| `app/orders/db.py` | Connection pool; password or Microsoft Entra token auth |
| `app/orders/migrate.py` | Applies SQL migrations once each |
| `app/payment_stub/main.py` | The fake payment processor |

## 6. Key design decisions

| # | Decision | Why | Trade-off |
|---|---|---|---|
| D1 | Azure Container Apps, not AKS / App Service | Revisions give free rollback, same image locally and in the cloud, consumption billing | Needs a container registry |
| D2 | PostgreSQL Flexible Server B1ms | Same engine locally, pure-Python driver, Entra auth (no password), can be **stopped** for a real outage | ~$15/month while running |
| D3 | One image, two services | One build and scan; fewer moving parts | Both services share dependencies |
| D4 | Readiness distinguishes critical vs non-critical dependencies | A payment outage must not remove orders-api from traffic | Callers must read `status` (`degraded`) |
| D5 | Timeouts on every dependency (DB connect 3 s, statement 5 s, payment 1 s/2 s) | A slow dependency must not hang the API | Slow-but-working payments over 2 s fail with 504 |
| D6 | Fault injection inside the app, token-protected, off by default | Repeatable, safe drills | State is per replica (in memory) |
| D7 | Manual DB spans instead of a psycopg auto-instrumentation package | Explicit, teachable, no version-pinning issues | One wrapper to maintain |
| D8 | Telemetry opt-in via connection string | Runs locally with zero Azure dependency | Local runs have logs only, no traces |
