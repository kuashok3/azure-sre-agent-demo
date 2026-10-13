# Runbook: HTTP 5xx Errors

**Use when:** the 5xx rate on `/api/*` exceeds 1–5%, the 5xx alert fires, or the smoke test fails with 5xx.
**Related:** FM-2, FM-3, FM-5, FM-6.

## 1. Which 5xx? (the error code tells you the layer)
```kusto
AppRequests
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and Url has "/api/" and toint(ResultCode) >= 500
| summarize n = count() by ResultCode, Name
```
```kusto
AppTraces
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and SeverityLevel >= 3
| summarize n = count(), sample = take_any(Message) by event = tostring(Properties.event), code = tostring(Properties.error_code)
```

| Code / error | Layer | Go to |
|---|---|---|
| 500 `internal_error`, `unhandled_exception` | Application code | §2 |
| 503 `database_unavailable` | PostgreSQL | [DATABASE_FAILURE](DATABASE_FAILURE.md) |
| 503 `payment_service_unavailable` / 504 `payment_service_timeout` | payment-stub | [DEPENDENCY_TIMEOUT](DEPENDENCY_TIMEOUT.md) |
| 502/503 from ingress with no AppRequests rows | Platform (no healthy replica) | §3 |

## 2. Application errors (500)
```kusto
AppExceptions
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api"
| summarize n = count(), first_seen = min(TimeGenerated), last_seen = max(TimeGenerated) by ExceptionType, OuterMessage
```
- `InjectedFaultError` → drill (`http_5xx`). Confirm with the `fault_enabled` audit event. Recover with `fault.py reset`.
- Anything else → did errors start right after a new revision? Then roll back (approval required).
- Dependencies healthy at the same time? That confirms the cause is in the app, not downstream.

## 3. Platform: requests not reaching the app
- Replica restarts / probe failures: `ContainerAppSystemLogs_CL` (name to verify in M6), revision health:
  `az containerapp revision list -n ca-orders-api -g rg-sredemo-app -o table`.
- Image pull or secret reference failures appear on new revisions.

## 4. Mitigations

| Action | Risk | Approval |
|---|---|---|
| Reset drill faults (`fault.py reset`) | none | Human operator |
| Roll back to the previous healthy revision | brief disruption | **Required** |
| Restart the current revision | in-flight requests fail; **clears in-memory fault state** | **Required** |

## 5. Verify
5xx rate < 0.5% for 10 min, smoke test passes, AppExceptions quiet. Record budget consumption (SERVICE_LEVELS §3).

## Prompts for Azure SRE Agent
- "orders-api is returning 5xx. Break down by status code and error code, tell me which layer is failing, and cite the query results."
- "Is the error rate correlated with a revision change, a fault_enabled event, or a dependency failure? Rank the hypotheses with your confidence and the evidence."
