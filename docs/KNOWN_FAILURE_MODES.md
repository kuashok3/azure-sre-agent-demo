# Known Failure Modes

Each row was **reproduced locally** with `scripts/validate_faults.py --include-docker` on
2026-10-12 unless marked otherwise. "Distinguishing evidence" separates the **root cause** from
**symptoms** that look alike.

## Symptom → likely cause matrix

| Symptom | Possible causes | First check |
|---|---|---|
| 5xx on all `/api/*`, readiness 503 | DB down (real), `db_connection_failure` fault, pool exhausted | `checks.database.error` in `/health/ready`; `psycopg.pool` warnings; fault audit log |
| 5xx on `/api/*`, readiness 200 `ready` | code bug / `http_5xx` fault | `AppExceptions` type + `unhandled_exception` logs |
| Only checkout fails (503/504), readiness `degraded` or `ready` | payment-stub down / slow / erroring | AppDependencies to payment-stub; payment-stub's own AppRequests |
| Everything slow, DB dependency durations normal | `latency` fault, CPU saturation, traffic spike | request vs dependency duration; request rate; replica CPU |
| Everything slow, DB dependency durations high | `db_latency` fault, slow DB, DB CPU/IO saturation | AppDependencies `postgresql` p95; PostgreSQL metrics |
| Many 402 | Large orders (business) | **Not an incident.** Check order totals |

## Catalogue

### FM-1 Application latency (`latency` fault / CPU saturation)
- **Trigger:** `fault.py enable latency --param delay_ms=1500` or load beyond capacity.
- **Symptoms:** `/api/*` duration up by ~delay. `/health/*` unaffected. No errors.
- **Distinguishing evidence:** request duration ≫ sum of dependency durations → the time is
  spent *inside* orders-api, not in PostgreSQL or payment-stub.
- **Runbook:** [HIGH_LATENCY](../runbooks/HIGH_LATENCY.md)

### FM-2 HTTP 500 from the application (`http_5xx` fault / bug)
- **Symptoms:** `500 internal_error`, `event=unhandled_exception` with stack trace,
  `ExceptionType = InjectedFaultError` for the drill. Readiness stays 200. Dependencies healthy.
- **Distinguishing evidence:** errors without dependency failures → cause is in app code or config.
  Check for a recent revision or deployment.
- **Runbook:** [HTTP_5XX_ERRORS](../runbooks/HTTP_5XX_ERRORS.md)

### FM-3 Database unreachable (`db_connection_failure` fault / real outage)
- **Symptoms:** `503 database_unavailable` on all DB-backed endpoints, readiness `503 not_ready`,
  `postgresql *` dependencies failing.
- **Distinguishing evidence:**
  - Synthetic: message contains `injected fault: db_connection_failure`, plus a `fault_enabled` audit log.
  - Real: message `Database unavailable (OperationalError|PoolTimeout)`, plus `psycopg.pool` connection
    warnings. In Azure, the server state is `Stopped`, or `is_db_alive` = 0 (PostgreSQL metric).
- **Recovery observed locally:** after `docker compose start postgres`, readiness returned to 200 on its own
  within seconds (the pool reconnects; no app restart needed).
- **Runbook:** [DATABASE_FAILURE](../runbooks/DATABASE_FAILURE.md)

### FM-4 Database slow (`db_latency` fault)
- **Symptoms:** DB-backed endpoints slow by ~delay per DB call. Checkout makes 2 instrumented DB calls (`get_order`, `set_payment_result`), so it slows by about 2× the delay.
- **Distinguishing evidence:** AppDependencies `postgresql` p95 rises together with AppRequests p95.
- **Note:** a delay above `DB_STATEMENT_TIMEOUT_MS` does **not** trigger the statement timeout, because the
  injected sleep happens in the client, not in SQL.
- **Runbook:** [HIGH_LATENCY](../runbooks/HIGH_LATENCY.md) → database branch

### FM-5 Payment dependency timeout (`payment_latency` fault)
- **Symptoms:** checkout `504 payment_service_timeout` after ~2 s (`PAYMENT_TIMEOUT_SECONDS`).
  The order stays `PENDING`. Other endpoints healthy. Readiness `ready` (the health probe is fast).
- **Distinguishing evidence:** orders-api's dependency call to payment-stub fails at ~2 s, **and**
  payment-stub's *own* AppRequests show ~5 s durations → the slowness is in payment-stub.
- **Runbook:** [DEPENDENCY_TIMEOUT](../runbooks/DEPENDENCY_TIMEOUT.md)

### FM-6 Payment dependency errors (`payment_errors` fault / real outage)
- **Symptoms:** checkout `503 payment_service_unavailable`.
  - Synthetic: payment-stub returns 503 `processor_unavailable`; readiness stays `ready`.
  - Real (stub stopped): connection errors; readiness `degraded`.
- **Runbook:** [DEPENDENCY_TIMEOUT](../runbooks/DEPENDENCY_TIMEOUT.md)

### FM-7 Traffic spike
- **Trigger:** `scripts/load.py --concurrency 50 --duration 120`.
- **Symptoms:** request rate up, latency up (local single worker: p50 ≈ 130 ms at ~145 req/s), errors
  only if saturation becomes severe.
- **Distinguishing evidence:** latency correlates with request count, with no faults active and no dependency errors.
- **Runbook:** [HIGH_LATENCY](../runbooks/HIGH_LATENCY.md) → capacity branch

### FM-8 Fault state differs across replicas [PLANNED-AZURE risk]
- Fault state is in memory **per replica**. With 2+ replicas, a fault affects only the share of requests
  hitting the replica that received the admin call. `fault.py list` can show "none" on another replica.
- **Mitigation:** run 1 replica during drills (decided in M4).

### FM-9 Stale alert (application healthy)
- An alert can still show "fired" after recovery. Always confirm the **current** state with
  `/health/ready` and the last 5–10 minutes of AppRequests before acting.

## Not failures
402 `payment_declined`, 404, 409, 422 and readiness `degraded` (on its own) are expected behaviour.
See [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md).
