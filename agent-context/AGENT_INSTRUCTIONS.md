# Operating Instructions for Azure SRE Agent: Contoso Orders

> How this file reaches the agent (verified product mechanisms, Phase 0): (1) upload to the agent's
> **knowledge base** so it is cited in answers; (2) the agent can also read it through the
> **GitHub repository connector**. Key facts may be pinned with `#remember`. Merely committing this
> file to git does **not** load it into the agent.

## Service summary
- **Contoso Orders** = `orders-api` (public, FastAPI) → `payment-stub` (internal) and PostgreSQL.
- Resource group in scope: **`rg-sredemo-app`** only. Non-production training environment.
- Critical journeys: create order (DB), checkout (DB + payment-stub).
- Health: `/health/live` (process), `/health/ready` (database **critical** → 503 `not_ready`;
  payment-stub **non-critical** → 200 `degraded`).
- Telemetry: Application Insights `appi-sredemo` on Log Analytics `log-sredemo`. Tables `AppRequests`,
  `AppDependencies` (`postgresql`, HTTP to payment-stub), `AppExceptions`, `AppTraces`
  (`Properties.event`, `Properties.correlation_id`, `Properties.error_code`). `AppRoleName` is
  `orders-api` or `payment-stub`.
- Docs to consult: SYSTEM_OVERVIEW, ARCHITECTURE, KNOWN_FAILURE_MODES, SERVICE_LEVELS, and the runbooks
  HIGH_LATENCY, HTTP_5XX_ERRORS, DATABASE_FAILURE, DEPENDENCY_TIMEOUT, RECOVERY_AND_ROLLBACK.

## How to investigate
1. **Establish current state first** (last 15 minutes): error rate, p95 latency, readiness, and
   whether the alert is still valid. Say so if the system is already healthy.
2. **Scope:** which endpoints, which role (`orders-api` vs `payment-stub`), and since when.
3. **Find what changed:** revisions or deployments, configuration, `AppTraces` events
   `fault_enabled`/`fault_disabled`/`faults_reset`, PostgreSQL server state.
4. **Separate symptom from cause:** compare request duration with dependency duration. Check the
   dependency's *own* telemetry (payment-stub AppRequests, PostgreSQL metrics). A 504 in orders-api
   is a symptom; slowness inside payment-stub is the cause.
5. **Form at least two hypotheses.** For each, state the supporting evidence, the contradicting evidence and
   what would confirm it. Give a confidence (high/medium/low).
6. **Quantify impact:** failed requests / total, affected journeys, error-budget consumption
   (SLO 99.5% availability; method in SERVICE_LEVELS).
7. **Recommend** the least risky reversible mitigation from the runbook, with its risk and rollback.

## Evidence rules
- Every claim about the system must cite a query result, metric, resource property or document.
  Include the KQL you ran.
- If data is missing, say "insufficient evidence" and name what would resolve it. **Do not guess.**
- 4xx responses (402 declined, 404, 409, 422) are **not** outages.
- Errors that mention `injected fault` are drills. Still investigate them properly, and report that the
  trigger was a fault injection.

## Actions
- **Allowed without approval:** read resources, metrics, logs; run KQL; summarise; draft reports.
- **Require human approval (Review mode):** restart a revision; shift traffic / roll back a revision;
  scale `ca-orders-api` or `ca-payment-stub` between 1 and 3 replicas; start the PostgreSQL server.
- **Never:** delete resources; change RBAC/identities; read Key Vault secret values; change
  networking/firewall; change SKUs/tiers; stop the database; disable alerts or diagnostics; call
  `/admin/faults`; act on anything outside `rg-sredemo-app`. Full list: RESOURCE_BOUNDARIES.md.

## Incident report format
Summary · Severity · Impact (numbers) · Timeline (UTC) · Root cause + evidence + confidence ·
Alternatives ruled out · Mitigation (proposed/approved/executed) · Verification · Follow-ups.
