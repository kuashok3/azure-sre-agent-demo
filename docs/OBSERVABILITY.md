# Observability

> Locally, logs are verified **[LIVE-LOCAL]**. Azure table and column names below follow the
> workspace-based Application Insights schema and are **expected, to be verified in M6** against
> real data. Until then, treat the KQL as unvalidated.

## 1. The three signals

| Signal | Answers | Ours |
|---|---|---|
| **Logs** | "What happened, in words?" | JSON lines on stdout → `AppTraces` (+ `ContainerAppConsoleLogs_CL` in Azure) |
| **Traces** (requests + dependencies) | "Where did the time go / which hop failed?" | FastAPI requests → `AppRequests`. DB and payment calls → `AppDependencies` |
| **Metrics** | "How much / how fast, as numbers over time?" | `orders_created`, `order_value_cents`, `checkout_results` → `AppMetrics`. Platform metrics for Container Apps and PostgreSQL |

## 2. Structured log format [LIVE-LOCAL]

```json
{"timestamp":"2026-10-11T19:22:50.098+00:00","level":"INFO","service":"orders-api","logger":"app.http",
 "message":"request completed","correlation_id":"599ce6e2...","trace_id":"...","event":"http_request",
 "http_method":"POST","http_path":"/api/v1/orders/<id>/checkout","http_status":200,"duration_ms":23.1}
```
`trace_id`/`span_id` appear only when telemetry is enabled. In Azure, custom fields land in
`AppTraces.Properties` (customDimensions).

### Log events (the `event` field)

| event | Level | Service | Meaning |
|---|---|---|---|
| `startup` / `shutdown` | INFO | orders-api | Process lifecycle, includes `version`, `git_sha`, `faults_enabled` |
| `telemetry_enabled` / `telemetry_disabled` | INFO | both | Whether App Insights export is on |
| `http_request` | INFO | both | One per request (not `/health/live`): method, path, status, duration_ms |
| `order_created` | INFO | orders-api | order_id, total_cents |
| `checkout_paid` / `checkout_declined` | INFO | orders-api | Checkout outcome |
| `client_error` | INFO | both | 4xx AppError with `error_code` |
| `app_error` | **ERROR** | both | 5xx AppError, e.g. `database_unavailable`, `payment_service_timeout` |
| `unhandled_exception` | **ERROR** + stack | both | Unexpected exception → 500 (includes the `http_5xx` fault) |
| `fault_enabled` / `fault_disabled` / `faults_reset` | **WARNING** | both | Audit trail of fault-injection changes |
| `payment_approved` / `payment_declined` | INFO | payment-stub | Payment outcome |
| `migration` / `migrations_complete` | INFO | migrate | Schema changes |
| (no event) logger `psycopg.pool` | WARNING | orders-api | Pool cannot connect: a strong signal of a **real** DB outage |

## 3. Correlation

| Identifier | Scope | Where |
|---|---|---|
| `X-Correlation-ID` / `correlation_id` | One client request, across orders-api → payment-stub | Response header, error body, every log line |
| `trace_id` = App Insights `OperationId` | Same request, end to end | AppRequests/AppDependencies/AppTraces/AppExceptions `OperationId` |

How to find everything about one failed request: take `correlation_id` from the error body,
search `AppTraces` for it, read its `OperationId`, then query all tables by that `OperationId`.

## 4. Telemetry table map [to verify in M6]

| Table | Key columns we use | Our data |
|---|---|---|
| `AppRequests` | `TimeGenerated, AppRoleName, Name, Url, ResultCode, Success, DurationMs, OperationId` | Every request except `/health/live`. `AppRoleName` = `orders-api` or `payment-stub` |
| `AppDependencies` | `AppRoleName, DependencyType, Name, Target, Success, ResultCode, DurationMs` | `postgresql <op>` spans; HTTP calls to payment-stub |
| `AppExceptions` | `ExceptionType, OuterMessage, ProblemId, OperationId` | Unhandled exceptions and recorded 5xx AppErrors |
| `AppTraces` | `Message, SeverityLevel, Properties` | Our log lines (`Properties.event`, `.correlation_id`, ...) |
| `AppMetrics` | `Name, Sum, ItemCount, Properties` | Business metrics |
| `ContainerAppConsoleLogs_CL` / `ContainerAppSystemLogs_CL` | platform | stdout and platform events (restarts, probe failures, revision changes). Exact names depend on the environment's log configuration |

## 5. Starter KQL [unvalidated until M6]

```kusto
// Error rate and volume per 5 minutes for the orders API
AppRequests
| where TimeGenerated > ago(1h) and AppRoleName == "orders-api" and Url has "/api/"
| summarize total = count(), failed = countif(toint(ResultCode) >= 500) by bin(TimeGenerated, 5m)
| extend error_rate_pct = round(100.0 * failed / total, 2)
| order by TimeGenerated asc
```
```kusto
// Latency percentiles per endpoint
AppRequests
| where TimeGenerated > ago(1h) and AppRoleName == "orders-api" and Url has "/api/"
| summarize p50 = percentile(DurationMs, 50), p95 = percentile(DurationMs, 95),
            p99 = percentile(DurationMs, 99), n = count() by Name
| order by p95 desc
```
```kusto
// Is a dependency the cause? Failures and latency by dependency
AppDependencies
| where TimeGenerated > ago(1h) and AppRoleName == "orders-api"
| summarize calls = count(), failed = countif(Success == false),
            p95_ms = percentile(DurationMs, 95) by DependencyType, Target
```
```kusto
// Fault-injection audit trail (synthetic incidents announce themselves here)
AppTraces
| where TimeGenerated > ago(24h) and tostring(Properties.event) in ("fault_enabled", "fault_disabled", "faults_reset")
| project TimeGenerated, AppRoleName, Message, fault = tostring(Properties.fault_name), params = tostring(Properties.fault_params)
```
More queries are in the runbooks and in [SERVICE_LEVELS.md](SERVICE_LEVELS.md). Phase 8 moves them into `kql/`.

## 6. Health endpoints as signals

| Endpoint | Used by | Meaning |
|---|---|---|
| `/health/live` | Container liveness probe, docker HEALTHCHECK | Process alive. Failing = restart the replica |
| `/health/ready` | Humans, smoke tests, SRE Agent. Probe use decided in M4 (open issue 8) | 503 = DB problem; `degraded` = payment problem |

## 7. Alerts [PLANNED-AZURE, M6]

| Alert | Signal | Initial threshold (illustrative) | Severity |
|---|---|---|---|
| High 5xx rate | AppRequests, orders-api `/api/*` | > 5% over 5 min with ≥ 20 requests | Sev2 |
| High latency | AppRequests p95 | > 1000 ms over 10 min | Sev3 |
| Dependency failures | AppDependencies failed | > 10 in 5 min | Sev2 |
| Database down | PostgreSQL `is_db_alive` metric or readiness | not alive for 5 min | Sev1 |
