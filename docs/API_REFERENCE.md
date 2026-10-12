# API Reference

Base URL: local `http://localhost:8080` · Azure: `https://<ca-orders-api FQDN>` (M5).
Interactive docs: `/docs` (Swagger UI), schema at `/openapi.json`.

## Common behaviour

- **Correlation:** send `X-Correlation-ID` (8–64 chars, `A-Z a-z 0-9 . _ -`) or one is generated.
  It is always echoed in the response header and included in error bodies and logs.
- **Timing:** the response header `X-Response-Time-Ms` gives the server-side duration.
- **Error body** (all application errors):
  ```json
  {"error": "database_unavailable", "message": "Database unavailable (OperationalError)", "correlation_id": "4f2c..."}
  ```
  Exception: input validation errors (422) use FastAPI's standard shape `{"detail": [...]}`.

## Health and info

| Method & path | Success | Failure | Notes |
|---|---|---|---|
| `GET /` | 200 service description | — | |
| `GET /health/live` | 200 `{"status":"alive"}` | process dead / no response | No dependency checks. Not exported as telemetry |
| `GET /health/ready` | 200 `ready` or `degraded` | 503 `not_ready` | Body: `checks.database` (critical), `checks.payment_service` (non-critical) with `status`, `latency_ms`, `error` |
| `GET /info` | 200 version, git_sha, build_time, environment, region, python, telemetry_enabled, faults_enabled | — | |

## Orders (`/api/v1`)

### `POST /api/v1/orders` → 201
```json
{"customer_id": "cust-001", "currency": "USD",
 "items": [{"sku": "WIDGET-1", "quantity": 2, "unit_price_cents": 1250}]}
```
Rules: `customer_id` 1–64 chars; `currency` ∈ USD, EUR, INR (default USD); 1–50 items; `sku`
1–64 chars `[A-Za-z0-9_-]`; `quantity` 1–100; `unit_price_cents` 1–10,000,000.
Response: the order (`id`, `customer_id`, `status`=`PENDING`, `currency`, `total_cents`,
`payment_reference`, `created_at`, `updated_at`, `items[]`).

### `GET /api/v1/orders/{id}` → 200 order · 404 · 422 (not a UUID)
### `GET /api/v1/orders?limit=20` → 200 `{"count": n, "orders": [... + item_count]}` (limit 1–100, newest first)
### `POST /api/v1/orders/{id}/checkout` → 200 order with `status=PAID`, `payment_reference=pay_…`
### `GET /api/v1/stats` → 200 `{"total_orders", "orders_by_status": {...}, "paid_revenue_cents"}`

## Status and error codes

| HTTP | `error` | Meaning | Counts against availability SLO? |
|---|---|---|---|
| 400/422 | (FastAPI `detail`) | Invalid input | No (client error) |
| 401 | `unauthorized` | Missing or wrong `X-Fault-Token` | No |
| 402 | `payment_declined` | Order total above payment limit | No (business outcome) |
| 404 | `order_not_found` / `unknown_fault` | Not found | No |
| 409 | `order_state_conflict` | Already paid | No |
| 422 | `invalid_fault_params` | Fault admin API: parameter out of range or unknown | No (admin API) |
| 500 | `internal_error` | Unhandled exception (includes the injected `http_5xx` fault) | **Yes** |
| 502 | `fault_forward_failed` | Fault admin could not reach payment-stub | No (admin API) |
| 503 | `database_unavailable` | PostgreSQL unreachable / pool exhausted / injected DB fault | **Yes** |
| 503 | `payment_service_unavailable` | payment-stub unreachable or returned 5xx | **Yes** |
| 504 | `payment_service_timeout` | payment-stub slower than `PAYMENT_TIMEOUT_SECONDS` | **Yes** |

## Fault admin API (demo only)

Mounted only if `FAULTS_ENABLED=true`. Header `X-Fault-Token` required. See [KNOWN_FAILURE_MODES.md](KNOWN_FAILURE_MODES.md).

| Method & path | Body | Result |
|---|---|---|
| `GET /admin/faults` | — | `{"available": [...], "active": [...]}` |
| `PUT /admin/faults/{name}` | `{"params": {"delay_ms": 1500}}` (optional) | enables the fault. 404 unknown, 422 bad params, 502 forward failed |
| `DELETE /admin/faults/{name}` | — | disables one fault |
| `DELETE /admin/faults` | — | **recovery**: disables all faults, including forwarded payment-stub faults |

## payment-stub (internal dependency)

| Method & path | Result |
|---|---|
| `POST /api/v1/payments` `{"order_id","amount_cents","currency"}` | 200 `{"payment_id","status":"APPROVED"}` · 402 `{"status":"DECLINED"}` if amount > `DECLINE_THRESHOLD_CENTS` · 503 `processor_unavailable` under the `errors` fault |
| `GET /health/live`, `/health/ready`, `/info` | 200 |
| `/admin/faults` | same API. Faults: `latency`, `errors` |
