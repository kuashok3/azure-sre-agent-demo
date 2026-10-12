# Dependencies

## Runtime dependency graph

```
orders-api
 ├── PostgreSQL ........ CRITICAL      (every /api/* call except checkout's payment step)
 │     timeouts: connect 3 s · wait for pooled connection 3 s · statement 5 s
 │     failure → 503 database_unavailable, /health/ready 503 not_ready
 └── payment-stub ...... NON-CRITICAL  (checkout only)
       timeouts: connect 1 s · read PAYMENT_TIMEOUT_SECONDS (default 2 s) · health 1 s
       failure → checkout 503/504, order stays PENDING; /health/ready 200 degraded
payment-stub
 └── (no dependencies)
```

| Dependency | Called by | Protocol | Telemetry (Azure) | Failure behaviour | Retries |
|---|---|---|---|---|---|
| PostgreSQL | orders-api `ObservedRepository` | psycopg 3, connection pool (min 1, max 5) | AppDependencies `DependencyType = postgresql`, name `postgresql <operation>` | `OperationalError`/`PoolTimeout` → 503 | None per request. The pool reconnects in the background (verified: recovers within seconds of `docker compose start postgres`) |
| payment-stub | orders-api `PaymentClient` | HTTP/JSON (`requests`) | AppDependencies HTTP, target = payment-stub host; also AppRequests of role `payment-stub` | 402/5xx/timeout mapped, see API_REFERENCE | None (the client retries the checkout) |
| Application Insights | both | HTTPS (OpenTelemetry exporter) | — | Telemetry is lost or delayed; **the app keeps serving** | exporter's own |
| Key Vault [PLANNED-AZURE] | Container Apps secret reference | managed identity | — | revision fails to start if the secret can't be resolved | platform |
| Microsoft Entra ID [PLANNED-AZURE] | orders-api (DB token) | `azure-identity` | — | new DB connections fail → 503 | SDK |

## Startup dependencies

- Local: `orders-api` starts only after `migrate` exits 0, which waits for `postgres` to be healthy.
- orders-api **does not crash** if the DB is down at startup: the pool opens in the background
  and readiness reports 503 until it connects.

## Software dependencies

Declared in `requirements.txt` (runtime) and `requirements-dev.txt` (tests/lint). Validated exact
versions are listed in [../CHECKPOINTS.md](../CHECKPOINTS.md).

| Package | Purpose |
|---|---|
| fastapi, uvicorn | Web framework and server |
| pydantic, pydantic-settings | Validation and env-var configuration |
| psycopg[binary], psycopg-pool | PostgreSQL driver and pool |
| requests | HTTP client (auto-instrumented by the Azure Monitor distro) |
| azure-identity | Entra token for PostgreSQL in Azure |
| azure-monitor-opentelemetry | Exports traces, logs, metrics to Application Insights |
| pytest, httpx, responses, ruff | Tests, test client, HTTP mocking, lint/format |
