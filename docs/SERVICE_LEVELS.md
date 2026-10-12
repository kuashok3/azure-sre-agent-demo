# Service Levels: SLIs, SLOs, SLA and Error Budgets

> ⚠️ **All targets here are illustrative training values.** This is not a customer SLA and makes
> no contractual promise. Queries are unvalidated until M6.

## 1. The four terms (beginner version)

| Term | Plain meaning | Our example |
|---|---|---|
| **SLI** (Service Level *Indicator*) | A measurement, usually *good events ÷ valid events* | "Share of order API requests that did not fail with 5xx" |
| **SLO** (Service Level *Objective*) | The target for an SLI over a time window, set by us | "99.5% of requests succeed, measured over 28 days" |
| **SLA** (Service Level *Agreement*) | A **contract** with customers, with penalties. Always looser than the SLO | **None.** This demo has no customers or contracts |
| **Error budget** | The failure the SLO *allows*: `1 − SLO` | 0.5% of requests may fail in 28 days |

Why this matters for incidents: the error budget turns "is this bad?" into a number.
An incident that burns 60% of the monthly budget in 15 minutes is urgent. A 0.01% blip is not.

## 2. SLIs

Common rules:
- **Scope:** `orders-api` requests whose URL contains `/api/`. Excluded: `/health/*`, `/info`,
  `/docs`, `/admin/*` (not customer traffic), and synthetic smoke tests if tagged later.
- **Good vs bad:** 5xx = bad. 4xx = good (the service behaved correctly; the client asked for something
  invalid, missing, or declined). **402 payment_declined counts as good**: it's a business outcome.
- **Source:** Application Insights `AppRequests` (server-side). Server-side SLIs miss requests that
  never reach the app (DNS, ingress outage). An availability test can cover that later (optional, M6).

| ID | SLI | Numerator (good) | Denominator (valid) | Window | Illustrative SLO |
|---|---|---|---|---|---|
| SLI-1 | **Availability** (request success) | `/api/*` requests with `ResultCode < 500` | all `/api/*` requests | 28 days rolling | **99.5%** |
| SLI-2 | **Latency: reads and creates** | successful non-checkout `/api/*` requests with `DurationMs < 500` | successful non-checkout `/api/*` requests | 28 days | **95%** under 500 ms |
| SLI-3 | **Latency: checkout** | successful checkout requests with `DurationMs < 1500` | successful checkout requests | 28 days | **95%** under 1.5 s |
| SLI-4 | **Checkout success** (business journey) | checkouts ending 200 or 402 | all checkout requests | 28 days | **99%** |
| SLI-5 | **Dependency health** (diagnostic, not user-facing) | successful `AppDependencies` calls per dependency | all calls | 1 h / 24 h | none. Used to find *causes* |
| SLI-6 | **Recovery time in drills** | — | — | per drill | Drill objective: detected < 10 min, recovered < 15 min after detection |

Why SLI-2 and SLI-3 are separate: checkout calls a second service, so it is naturally slower.
One shared threshold would either hide slow reads or flag every checkout.

## 3. Error budget maths

**Request-based budget** (what we use):
`allowed_bad = (1 − SLO) × total_valid_requests`

Example: 28 days at an average of 2 req/s = 4,838,400 requests.
Budget at 99.5% = 0.005 × 4,838,400 = **24,192 failed requests** allowed.

**Time-based view** (for intuition): 0.5% of 28 days = **201.6 minutes** of total outage.

### Worked example: a drill consuming the budget

Fault `http_5xx` with `error_rate=0.3` for 15 minutes at 2 req/s:
- requests = 15 × 60 × 2 = 1,800; failed ≈ 0.3 × 1,800 = **540**
- budget consumed = 540 / 24,192 = **2.2%** of the 28-day budget
- **burn rate** = observed error rate ÷ allowed error rate = 30% ÷ 0.5% = **60×**. At this pace the
  whole 28-day budget would be gone in 28 days ÷ 60 ≈ **11.2 hours**.

At low traffic (a demo with only ~0.2 req/s), the same 540 failures could exceed a small month's
whole budget. **The budget is relative to traffic**, which is why we report both absolute numbers and
percentages.

### Burn-rate alerting (concept; implemented in M6 if affordable)

| Window | Burn rate | Meaning | Action |
|---|---|---|---|
| 1 h | > 14.4× | 2% of 28-day budget gone in 1 h | Page (Sev2) |
| 6 h | > 6× | 5% gone in 6 h | Ticket (Sev3) |

## 4. Queries [unvalidated until M6]

```kusto
// SLI-1 availability + error budget over a chosen window
let slo = 0.995;
AppRequests
| where TimeGenerated > ago(28d) and AppRoleName == "orders-api" and Url has "/api/"
| summarize valid = count(), bad = countif(toint(ResultCode) >= 500)
| extend sli = 1.0 - todouble(bad) / valid,
         budget_requests = (1 - slo) * valid,
         budget_consumed_pct = round(100.0 * bad / ((1 - slo) * valid), 1)
```
```kusto
// SLI-2 / SLI-3 latency compliance
AppRequests
| where TimeGenerated > ago(28d) and AppRoleName == "orders-api" and Url has "/api/" and toint(ResultCode) < 500
| extend journey = iff(Url has "/checkout", "checkout", "reads_creates"),
         threshold = iff(Url has "/checkout", 1500.0, 500.0)
| summarize total = count(), fast = countif(DurationMs < threshold) by journey
| extend compliance_pct = round(100.0 * fast / total, 2)
```
```kusto
// Burn rate over the last hour
let slo = 0.995;
AppRequests
| where TimeGenerated > ago(1h) and AppRoleName == "orders-api" and Url has "/api/"
| summarize err = todouble(countif(toint(ResultCode) >= 500)) / count()
| extend burn_rate = round(err / (1 - slo), 1)
```

## 5. Validating numbers independently

Check SLI numbers from a second source:
1. `scripts/load.py` prints its own success ratio and p50/p95/p99 (client-side). Compare them with the
   KQL for the same time window. Client-side latency is higher (it includes the network).
2. Count injected failures: with `error_rate=1.0` for N requests, expect exactly N 500s.
3. Recalculate the budget maths in this file by hand from the query's `valid` and `bad`.
