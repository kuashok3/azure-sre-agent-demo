# Checkpoints & Open Issues

| Milestone | Status | Date | Evidence / notes |
|---|---|---|---|
| Phase 0 research | ✅ Done | 2026-10-12 | docs/00_PHASE0_BLUEPRINT.md |
| M0 Prerequisites | ⏳ In progress | 2026-10-12 | Azure CLI installed + logged in; providers registered (DBforPostgreSQL was registering); signed in as Entra work account (org-domain UPN, no #EXT#) ✅; SRE Agent region list populated ✅; AAU pricing reviewed by architect ✅; budget amount USD 50/month decided ✅ (created in M4 Step 3). **Done** |
| M1 Local app | ✅ Done (verified on architect laptop) | 2026-10-12 | ruff clean; 53 unit + 3 integration tests pass; compose stack healthy; `smoke_test.py` 13/13; JSON logs with correlation_id propagated orders-api → payment-stub. Commit 2739c83 |
| M2 Local faults | ✅ Done (code verified) | 2026-10-12 | `validate_faults.py --include-docker` all scenarios pass incl. real Postgres/payment-stub outages + recovery; admin API 401 without token, 404 when disabled; load test 145 req/s, 100% success, p95 ≈ 200 ms |
| M3 Docs & SLOs | ✅ Written, awaiting team review | 2026-10-12 | 13 docs + 5 runbooks + 2 agent-context files; log events and error codes cross-checked against code; Azure-specific parts marked [PLANNED-AZURE]; KQL unvalidated until M6. Acceptance needs a second-person review |
| M4 Azure infra | ⏳ Templates ready, not deployed | 2026-10-12 | `infra/main.bicep` (+ module), `infra/budget.bicep` compile and pass `az bicep lint`; PostgreSQL B1ms/v16 and Container Apps confirmed available in eastus2 and centralindia; guide in docs/DEPLOYMENT.md §2. Region decided: **eastus2**. Architect runs the commands, Claude guides. Steps 1–4 done 2026-10-12: RG + `budget-sredemo` created; what-if = 14 to create, 0 modify/delete, all in rg-sredemo-app (suffix `uuouh`). Step 5 attempt 1 (2026-10-13): 6 resources created, PostgreSQL **B1ms failed `SkuNotAvailable`** although `list-skus` showed it available; no leftover server. Decision: retry with `postgresSkuName=Standard_B2s` (new template parameter) |
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
| 5 | ~~Folder inside Desktop git repo~~ Resolved: own repo (`git init -b main`) | Architect | M1 |
| 6 | Host ports moved to 8080/8081/5434 because the local "observio" stack uses 8000-8002/5433 | All | — |
| 7 | ~~Fault state per replica~~ Decided: apps fixed at 1 replica (`infra/modules/container-app.bicep`) | Architect | M4 |
| 8 | ~~Readiness probe design~~ Decided: liveness and readiness probes both use `/health/live`; `/health/ready` stays for humans/agent | Architect | M4 |
| 9 | `DB_AUTH_MODE=entra` (managed-identity token for PostgreSQL) is written but can only be verified in Azure | App & Deploy | M5 |
| 10 | Single uvicorn worker: p50 rises to ~130 ms at ~145 req/s locally. Useful for spike demos; revisit replica/CPU sizing in M4 | App & Deploy | M4 |
| 11 | Starlette prints a deprecation warning about `httpx` in TestClient (tests unaffected) | — | revisit on upgrade |
| 12 | Team receives code as a `git archive` zip (verified 2026-10-12: 72 KB, no .env/.venv, fresh setup + 53 tests pass). Move to GitHub in M11 | Architect | M11 |
| 14 | **Shared subscription** ("Bangalore Azure PayAsYouGo", 13 other RGs). **4 SRE Agents already exist** (SRE_Agent_test, test_sre-agent_sept). The 30-day trial (max 3 agents/account) is likely used up, so plan for always-on billing from creation (~96 AAU/day). Create the agent late, delete it promptly | Architect | M7 |
| 15 | Azure Monitor incident integration needs Monitoring Contributor at **subscription** scope, so our agent could ack/close other teams' alerts. Decide an alternative (scoped response-plan filters, HTTP trigger, or manual alert hand-off) in Phase 6 | Architect | M7 |
| 16 | Existing subscription budget `dev_env_monthly_budget` (USD 100) is shared; ours is tag-filtered `budget-sredemo` | Architect | — |
| 13 | Windows PowerShell 5 `Get-Content`/`Set-Content` mangles UTF-8 files. Edit files with an editor, or use `-Encoding utf8` on both read and write | All | — |
