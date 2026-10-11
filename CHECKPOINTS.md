# Checkpoints & Open Issues

| Milestone | Status | Date | Evidence / notes |
|---|---|---|---|
| Phase 0 research | ✅ Done | 2026-10-12 | docs/00_PHASE0_BLUEPRINT.md |
| M0 Prerequisites | ⏳ In progress | 2026-10-12 | Azure CLI installed + logged in; providers registered (DBforPostgreSQL was registering); signed in as Entra work account (org-domain UPN, no #EXT#) ✅. Pending: agent region list, $/AAU, budget |
| M1 Local app | ✅ Done (verified on architect laptop) | 2026-10-12 | ruff clean; 53 unit + 3 integration tests pass; compose stack healthy; `smoke_test.py` 13/13; JSON logs with correlation_id propagated orders-api → payment-stub |
| M2 Local faults | ✅ Done (code verified) | 2026-10-12 | `validate_faults.py --include-docker` all scenarios pass incl. real Postgres/payment-stub outages + recovery; admin API 401 without token, 404 when disabled; load test 145 req/s, 100% success, p95 ≈ 200 ms |
| M3 Docs & SLOs | ⬜ | | |
| M4 Azure infra | ⬜ | | |
| M5 Azure app | ⬜ | | |
| M6 Telemetry | ⬜ | | |
| M7 Agent baseline | ⬜ | | Create agent no earlier than this milestone (30-day trial clock) |
| M8 Incidents | ⬜ | | |
| M9 Multi-agent | ⬜ | | |
| M10 Remediation & governance | ⬜ | | |
| M11 CI/CD | ⬜ | | `.github/workflows/ci.yml` written but **not yet run on GitHub** |
| M12 Capstone & cleanup | ⬜ | | |

## Validated dependency versions (M1, Python 3.13.7 host / 3.13 slim image)
fastapi 0.143.0 · uvicorn 0.54.0 · pydantic 2.14.1 · pydantic-settings 2.15.0 · psycopg 3.3.6 ·
psycopg-pool 3.3.3 · requests 2.34.2 · azure-identity 1.26.0 · azure-monitor-opentelemetry 1.8.11 ·
pytest 8.4.2 · httpx 0.28.1 · responses 0.26.3 · ruff 0.17.0 · PostgreSQL 16 (alpine)

## Open issues

| # | Issue | Owner | Resolve by |
|---|---|---|---|
| 1 | $/AAU price unverified (pricing page shows placeholder) | Architect | M0 |
| 2 | ~~Confirm Entra work account~~ Resolved 2026-10-12 | Architect | M0 |
| 3 | Knowledge-base UI location and limits differ between doc pages | SRE Agent engineer | M7 |
| 4 | ~~Azure CLI not installed~~ Resolved 2026-10-12 | Architect | M0 |
| 5 | ~~Folder inside Desktop git repo~~ Resolved: own repo (`git init -b main`), nothing committed yet | Architect | M1 |
| 6 | Host ports moved to 8080/8081/5434 because the local "observio" stack uses 8000-8002/5433 | All | — |
| 7 | Fault state is in-memory **per replica**. In Azure run 1 replica during fault demos, or faults hit only some requests | Architect | M4 |
| 8 | Readiness probe design for Container Apps: a DB outage makes `/health/ready` 503, so the replica is removed from traffic and app telemetry goes quiet. Decide which probe paths to use in M4 | Architect | M4 |
| 9 | `DB_AUTH_MODE=entra` (managed-identity token for PostgreSQL) is written but can only be verified in Azure | App & Deploy | M5 |
| 10 | Single uvicorn worker: p50 rises to ~130 ms at ~145 req/s locally. Useful for spike demos; revisit replica/CPU sizing in M4 | App & Deploy | M4 |
| 11 | Starlette prints a deprecation warning about `httpx` in TestClient (tests unaffected) | — | revisit on upgrade |
