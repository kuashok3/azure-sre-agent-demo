# Runbook: High Latency

**Use when:** p95 of `/api/*` above SLO thresholds (500 ms reads/creates, 1500 ms checkout), the latency alert
fires, or users report slowness. **Related:** FM-1, FM-4, FM-7 in [KNOWN_FAILURE_MODES](../docs/KNOWN_FAILURE_MODES.md).

> Azure commands are **[PLANNED-AZURE]**: names are from RESOURCE_INVENTORY, verified in M5.

## 1. Confirm and scope (5 min)
- Is it still happening? Look at the last 15 minutes, not just the alert.
- Which endpoints? All of them (process-wide) or only checkout (payment path) or only DB-backed?
```kusto
AppRequests
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and Url has "/api/"
| summarize p95 = percentile(DurationMs, 95), n = count() by Name, bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```
Local equivalent: `python scripts\load.py --duration 15 --concurrency 5` and read p95.

## 2. Where is the time spent? (symptom vs cause)
```kusto
// Compare request duration with the dependency time inside the same operation
let reqs = AppRequests
  | where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and Url has "/api/"
  | project OperationId, req_ms = DurationMs, Name;
let deps = AppDependencies
  | where TimeGenerated > ago(30m) and AppRoleName == "orders-api"
  | summarize dep_ms = sum(DurationMs), db_ms = sumif(DurationMs, DependencyType == "postgresql") by OperationId;
reqs | join kind=leftouter deps on OperationId
| summarize p95_req = percentile(req_ms, 95), p95_dep = percentile(dep_ms, 95), p95_db = percentile(db_ms, 95) by Name
```

| Finding | Likely cause | Go to |
|---|---|---|
| `req ≈ dep`, and db_ms high | Database slow | §3a |
| `req ≈ dep`, payment calls high | Payment-stub slow | [DEPENDENCY_TIMEOUT](DEPENDENCY_TIMEOUT.md) |
| `req ≫ dep` | Time spent inside orders-api | §3b |

## 3a. Database branch
- Synthetic? `AppTraces` with `event == "fault_enabled"` and `fault_name == "db_latency"`.
- Real? PostgreSQL metrics: CPU %, active connections, storage IO. Look for slow queries.
- Mitigation: reset the fault (drill), or scale the DB tier (**approval + cost**, normally out of scope for the demo).

## 3b. Application branch
- Synthetic `latency` fault? Check the audit log or `python scripts/fault.py list`.
- Traffic spike? Request count per minute vs baseline.
- CPU saturation? Container Apps metrics: CPU/memory per replica, replica count.
- Recent deployment? `az containerapp revision list -n ca-orders-api -g rg-sredemo-app -o table`.

## 4. Mitigations

| Action | Command | Risk | Approval |
|---|---|---|---|
| Reset drill faults | `python scripts/fault.py reset --base-url <url>` | none | Human operator (agent has no token) |
| Scale out within 1–3 replicas | `az containerapp update -n ca-orders-api -g rg-sredemo-app --min-replicas 2 --max-replicas 3` | cost; fault state per replica | **Required** |
| Roll back a bad revision | see [RECOVERY_AND_ROLLBACK](RECOVERY_AND_ROLLBACK.md) | brief disruption | **Required** |
| Change DB SKU | — | cost, restart | **Prohibited for the agent**; human decision only |

## 5. Verify recovery
p95 back under threshold for ≥ 10 min; `scripts/smoke_test.py` passes; no active faults.

## Prompts for Azure SRE Agent
- "orders-api latency is high. Compare request duration with dependency duration over the last 30 minutes and tell me whether the time is spent in PostgreSQL, payment-stub, or inside the app. Show the KQL you used."
- "Was there a deployment, revision change or fault_enabled event before latency rose?"
