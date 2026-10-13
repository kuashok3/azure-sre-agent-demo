# Runbook: Payment Dependency Timeout / Errors

**Use when:** checkout returns `504 payment_service_timeout` or `503 payment_service_unavailable`,
or readiness shows `degraded`. **Related:** FM-5, FM-6.

## 1. Key idea: whose problem is it?
orders-api gives up after `PAYMENT_TIMEOUT_SECONDS` (2 s). The **symptom** is in orders-api.
The **cause** is usually in payment-stub. Prove it by looking at payment-stub's *own* telemetry.

```kusto
// orders-api's view of the dependency
AppDependencies
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and DependencyType has "HTTP" and Target has "payment"
| summarize calls = sum(ItemCount), failed = sumif(ItemCount, Success == false), p95 = percentile(DurationMs, 95) by ResultCode
```
```kusto
// payment-stub's own view
AppRequests
| where TimeGenerated > ago(30m) and AppRoleName == "payment-stub" and Url has "/api/v1/payments"
| summarize n = sum(ItemCount), p95 = percentile(DurationMs, 95), errors = sumif(ItemCount, toint(ResultCode) >= 500) by bin(TimeGenerated, 5m)
```

| orders-api sees | payment-stub sees | Conclusion |
|---|---|---|
| failures at ~2000 ms | requests ~5000 ms, 200 | payment-stub slow (`payment_latency` / real slowness) |
| 503 quickly | 503 `processor_unavailable` | payment-stub erroring (`payment_errors`) |
| connection errors | **no requests at all** | payment-stub down / unreachable (readiness `degraded`) |
| failures | requests fast and 200 | network between them, or wrong `PAYMENT_BASE_URL` |

## 2. Business impact
- Only **checkout** is affected. Order creation and reads keep working.
- Orders stay `PENDING` and can be retried after recovery (no double charge: the paid-state update is conditional).

## 3. Mitigations

| Action | Command | Approval |
|---|---|---|
| Reset drill faults | `python scripts/fault.py reset` (forwards to payment-stub) | Human operator |
| Restart / roll back payment-stub revision | `az containerapp revision list -n ca-payment-stub -g rg-sredemo-app -o table` then restart or activate | **Required** |
| Start a stopped stub (local) | `docker compose start payment-stub` | Human operator |
| Raise `PAYMENT_TIMEOUT_SECONDS` | hides the problem and slows checkout | **Not recommended**, human decision only |

## 4. Verify
Checkout 200 for a new order; the earlier `PENDING` order checks out successfully on retry; readiness `ready`.

## Prompts for Azure SRE Agent
- "Checkout is failing with 504. Using both orders-api dependency telemetry and payment-stub request telemetry, decide whether the root cause is in orders-api, the network, or payment-stub."
