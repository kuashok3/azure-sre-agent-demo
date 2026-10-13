# SRE Agent tests: Level 1 (understanding) and Level 2 (telemetry)

Run in the agent chat at sre.azure.com (agent `sre-sredemo`). One question per new thread keeps
answers independent. Record each result in the table at the bottom.
Cost: Microsoft's example puts a "quick question" at ~1–4 AAU on Anthropic models, so this sheet costs
roughly 30–60 AAU of the 500 AAU monthly cap.

**Pass criteria for every test:** facts match the "Expected" column; the agent cites evidence (doc,
resource, or the KQL it ran); it invents no resources; if unsure, it says so.

## Level 1: does it understand the system?

| ID | Prompt | Expected (verified facts) | Red flags |
|---|---|---|---|
| L1-01 | `What does the application in resource group rg-sredemo-app do? Cite your sources.` | Contoso Orders: order API (`orders-api`, FastAPI) creating orders and checking them out via `payment-stub`, data in PostgreSQL. Cites repo docs (SYSTEM_OVERVIEW/README) | Generic description with no citation |
| L1-02 | `Which Azure resources host this application, and in which region?` | `ca-orders-api` (public) and `ca-payment-stub` (internal) in `cae-sredemo`; `psql-sredemo-uuouh` (B1ms, PG16); `crsredemouuouh`; `kv-sredemo-uuouh`; `appi-sredemo` + `log-sredemo`; `id-orders-api`; **centralindia** | Resources from other teams' groups; wrong region |
| L1-03 | `What are the critical dependencies of orders-api, and what happens when each fails?` | PostgreSQL **critical** → 503 `database_unavailable`, readiness 503. payment-stub **non-critical** → checkout 503/504, readiness `degraded` 200, order stays PENDING | Treats payment-stub as critical |
| L1-04 | `Where are the logs, traces and metrics for orders-api, and which tables should I query?` | Workspace `log-sredemo` via `appi-sredemo`; `AppRequests`, `AppDependencies`, `AppTraces` (`Properties.event`), `AppExceptions`; Container Apps logs `ContainerAppConsoleLogs_CL` | Classic table names only, with no workspace |
| L1-05 | `What health endpoints does orders-api expose and what does each one mean?` | `/health/live` = process alive; `/health/ready` = DB critical (503 `not_ready`), payment non-critical (200 `degraded`); `/info` = version | Mixes up live and ready |

## Level 2: can it use real telemetry?

| ID | Prompt | Expected (checked with `scripts/run_kql.ps1`) | Red flags |
|---|---|---|---|
| L2-01 | `Find errors from orders-api in the last 24 hours. Group them by status code and error code, show the KQL you used, and tell me whether any were caused by fault injection.` | 500 `InjectedFaultError` (http_5xx), 503 `database_unavailable` (injected), 504 `payment_service_timeout`, 503 `payment_service_unavailable`; large 5xx burst 13:56–14:06 UTC on 2026-10-13 (alert test); identifies `fault_enabled` audit events | Misses the injected-fault evidence; no query shown |
| L2-02 | `Summarise orders-api latency for the last 24 hours: p50 and p95 per endpoint.` | Matches `kql/01_latency_by_endpoint.kql -Lookback 24h` (checkout slowest normally; drills inflate some p95s) | Numbers that don't match the KQL |
| L2-03 | `What is orders-api's error rate right now (last 15 minutes)? Is anything currently broken?` | ~0% / healthy (faults were reset); distinguishes *now* from the earlier drill | Reports the old drill as a current outage |
| L2-04 | `Which dependencies does orders-api call, and how healthy are they over the last 24 hours?` | PostgreSQL (`psql-sredemo-uuouh...|orders`) and `ca-payment-stub`, with failure counts from the drills; ideally ignores `settings.sdk.monitor.azure.com` | Lists `fastapi.*` InProc spans as dependencies |
| L2-05 | `Checkout is returning HTTP 504. Which runbook applies and what are its first steps?` | `runbooks/DEPENDENCY_TIMEOUT.md`: compare orders-api's dependency view with payment-stub's own requests | Invents a runbook |

## Results log

| ID | Date | Pass/Fail | Evidence cited? | Notes (wrong facts, cost from Settings › Agent consumption) |
|---|---|---|---|---|
| L1-01 | | | | |
| L1-02 | | | | |
| L1-03 | | | | |
| L1-04 | | | | |
| L1-05 | | | | |
| L2-01 | | | | |
| L2-02 | | | | |
| L2-03 | | | | |
| L2-04 | | | | |
| L2-05 | | | | |
