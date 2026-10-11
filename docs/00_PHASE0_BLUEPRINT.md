# Phase 0 — Azure SRE Agent Capability Verification & Project Blueprint

> Research date: **2026-10-12**. Sources: Microsoft Learn `learn.microsoft.com/azure/sre-agent/*` (pages dated Mar–Sep 2026) and `azure.microsoft.com/pricing/details/sre-agent/`.
> Everything marked **[VERIFIED]** was read from an official page on the research date. **[UNVERIFIED]** means we have not confirmed it yet and must check it at the named milestone. Product UIs change; re-check the linked page before each hands-on step.

---

## 1. Learning objective

By day 10 the team can: run an instrumented order-processing service locally, deploy it to Azure without AKS, measure it with SLIs/SLOs in Application Insights + Log Analytics, connect **Azure SRE Agent** to it through supported mechanisms (resource scope, telemetry connectors, GitHub connector, knowledge base, custom agents, response plans), inject controlled failures, and have the agent investigate and propose fixes — with a human approving every write action.

---

## 2. Verified capabilities of Azure SRE Agent

### 2.1 What it is

An Azure resource (`Microsoft.App/agents`) that hosts an LLM-driven operations agent. It reads Azure resource state, Azure Monitor / App Insights / Log Analytics telemetry, source code, and incidents, then explains problems, proposes root causes, and (if permitted) runs mitigations. Portal: **https://sre.azure.com**. [VERIFIED — [overview](https://learn.microsoft.com/azure/sre-agent/overview)]

### 2.2 Capability classification

| Capability | Classification | Notes / source |
|---|---|---|
| Chat-based investigation of Azure resources | **Native** | [overview](https://learn.microsoft.com/azure/sre-agent/overview) |
| Query Log Analytics / App Insights (KQL) | **Native** (built-in, no setup); optional **connector** for lower latency/tokens | [log-analytics-app-insights](https://learn.microsoft.com/azure/sre-agent/log-analytics-app-insights) |
| Azure Monitor alerts → automatic investigation threads | **Native integration** (Builder › Incident platform). Scans every 1 min; merges repeat firings | [azure-monitor-alerts](https://learn.microsoft.com/azure/sre-agent/azure-monitor-alerts) |
| Incident response plans (filter by severity etc.) | **Native** | [incident-response-plans](https://learn.microsoft.com/azure/sre-agent/incident-response-plans) |
| Review vs Autonomous run modes | **Native**, set per response plan / scheduled task. **Response-plan default is Autonomous** — we must set Review explicitly | [run-modes](https://learn.microsoft.com/azure/sre-agent/run-modes) |
| Approve/Deny buttons for Azure write ops | **Native**, only for Azure infra operations; only *SRE Agent Administrator* can approve | [run-modes](https://learn.microsoft.com/azure/sre-agent/run-modes) |
| Tool access policies (allow / ask / deny per tool) | **Native** | [tool-access-policies](https://learn.microsoft.com/azure/sre-agent/tool-access-policies) |
| Agent hooks (governance checkpoints) | **Native** | [agent-hooks](https://learn.microsoft.com/azure/sre-agent/agent-hooks) |
| **Custom agents** (a.k.a. subagents) with handoffs | **Native**. Fields: Name, Instructions, Handoff Description, Custom Tools, Built-in Tools, Handoff Agents, optional Knowledge base. Invoked with `/agent` or by triggers; share one conversation context | [sub-agents](https://learn.microsoft.com/azure/sre-agent/sub-agents) |
| Skills, Python tools, MCP servers, plugin marketplace | **Native extension points** | [overview](https://learn.microsoft.com/azure/sre-agent/overview) |
| Knowledge base (upload runbooks / docs) | **Native**. ⚠ Docs disagree on location and limits (Builder › Knowledge base, 16 MB, many formats **vs** Settings › Knowledge Base › Files, 50 MB, .md/.txt) — verify in UI on Day 5 | [memory](https://learn.microsoft.com/azure/sre-agent/memory), [sub-agents](https://learn.microsoft.com/azure/sre-agent/sub-agents) |
| GitHub repo connector (agent explores code for "deep context") | **Native integration** (OAuth, PAT, or BYO GitHub App) | [create-and-set-up](https://learn.microsoft.com/azure/sre-agent/create-and-set-up) |
| Memory: `#remember`, `#retrieve`, `#forget`; session insights; `memories/synthesizedKnowledge/overview.md` | **Native** | [memory](https://learn.microsoft.com/azure/sre-agent/memory) |
| Scheduled tasks, HTTP triggers | **Native** | [scheduled-tasks](https://learn.microsoft.com/azure/sre-agent/scheduled-tasks) |
| Teams / Outlook notifications, PagerDuty / ServiceNow | **Documented integrations** (we will not use PagerDuty/ServiceNow) | [connectors](https://learn.microsoft.com/azure/sre-agent/connectors) |
| IaC deployment of the agent (Bicep/Terraform/azd) | **Documented**, via `github.com/microsoft/sre-agent` templates | [deploy-iac](https://learn.microsoft.com/azure/sre-agent/deploy-iac) |
| Audit of agent actions | **Native** | [audit-agent-actions](https://learn.microsoft.com/azure/sre-agent/audit-agent-actions) |
| App Service & Container Apps troubleshooting tutorials | **Documented** (slot-swap rollback, revision rollback) | [ACA tutorial](https://learn.microsoft.com/azure/sre-agent/troubleshoot-azure-container-apps) |
| Our order-service app, fault injection, SLO queries, runbooks, load script | **Custom — we build** | this repo |
| A strict "6 agents + orchestrator" pipeline with guaranteed sequencing | **Partially native**: custom agents + handoff chains + main-agent orchestration exist; exact sequencing is LLM-driven, not a deterministic workflow engine. We will test and document behavior | [sub-agents](https://learn.microsoft.com/azure/sre-agent/sub-agents) |
| Per-token AAU dollar price | **[UNVERIFIED]** — pricing page shows `$-`; check Azure pricing calculator for our region | [pricing](https://azure.microsoft.com/pricing/details/sre-agent/) |

### 2.3 Prerequisites (must be true before Day 5)

| # | Requirement | Why | Source |
|---|---|---|---|
| P1 | **Owner** (or Contributor + User Access Administrator) on the subscription/RG | Portal assigns roles to the agent's identity and you | [create-and-set-up](https://learn.microsoft.com/azure/sre-agent/create-and-set-up) |
| P2 | Signed in with a **Microsoft Entra work/school account**, not a personal Microsoft account (MSA) | **Personal accounts cannot authorize on-behalf-of (OBO) elevation**, which is how a Reader-level agent performs approved writes | [permissions](https://learn.microsoft.com/azure/sre-agent/permissions) |
| P3 | `*.azuresre.ai` reachable from the browser (corporate proxy!) | Agent portal + data plane | [create-and-set-up](https://learn.microsoft.com/azure/sre-agent/create-and-set-up) |
| P4 | Region dropdown at sre.azure.com › Create agent is **not empty** | Empty = subscription not registered; file a registration request | [supported-regions](https://learn.microsoft.com/azure/sre-agent/supported-regions) |
| P5 | Trial eligibility understood (see §2.5) | Biggest cost lever | [evaluate](https://learn.microsoft.com/azure/sre-agent/evaluate) |
| P6 | Each teammate gets an SRE Agent role on the agent resource. **Owner/Contributor do NOT grant SRE Agent data actions** | Chat/approve/upload are data actions | [user-roles](https://learn.microsoft.com/azure/sre-agent/user-roles) |

### 2.4 Identity & authorization model [VERIFIED]

- **Agent identity**: deployment creates a **user-assigned managed identity (UAMI)** (used for RBAC + connectors) and enables a system-assigned identity (agent infrastructure). With no resource scope, the UAMI has **no permissions**.
- **Permission levels** when adding a resource group: **Reader** (Reader + Monitoring Reader + Log Analytics Reader + type-specific reader roles) or **Privileged** (adds type-specific contributor roles, e.g. Container Apps Contributor).
- **Azure Monitor incident integration** needs **Monitoring Contributor at subscription scope** (acknowledge/close alerts). This is a write role on monitoring objects across the subscription — a conscious, documented exception to least privilege.
- **OBO fallback**: if the UAMI lacks a permission, the agent asks an *SRE Agent Administrator* to lend their credentials for that one operation; not retained afterwards.
- **User roles** (on the agent resource): SRE Agent **Reader**, **Standard User**, **Author**, **Administrator**. Only Administrators approve actions. Author alone cannot chat or upload knowledge.

### 2.5 Cost model [VERIFIED except $/AAU]

| Component | Rate | Notes |
|---|---|---|
| Always-on | **4 AAU per agent-hour** (≈ 2,920 AAU/month) | Billed from creation until **deletion**. *Stopping* the agent does **not** stop it |
| Active flow | Token-metered, per model (e.g. per 1M tokens: GPT-5.2 35 in / 280 out; Claude Opus 4.6 100 in / 500 out) | Doc examples: quick question ≈ 1.3–3.8 AAU; incident investigation ≈ 12–35 AAU; full remediation ≈ 30–87 AAU |
| Active-flow cap | Settings › Agent consumption, **min 500 AAU/month** | Caps active flow only |
| Trial | New customers: **always-on waived for 30 days**, clock starts at **first agent creation**, max 3 agents (deleted ones still count) | Active flow still billed. Converts to full price automatically on day 31 |
| $/AAU | **[UNVERIFIED]** | Check calculator for chosen region before Day 5 |

**Consequence for the plan:** do **not** create the agent until Day 5 (after the app is deployed and telemetry validated), run Days 5–10 inside the trial, and **delete the agent** before trial day 30 unless we decide to keep paying.

### 2.6 Regions [VERIFIED]

Agent regions include `eastus2`, `centralindia`, `southindia`, `swedencentral`, `westus2`, `uksouth`, … (22 total). The agent region only determines where agent compute runs; it can manage resources in any region it has RBAC on. Region cannot be changed after creation.

---

## 3. Recommended architecture

### 3.1 Application: "Contoso Orders" — order-processing API (backend-only)

FastAPI service exposing orders CRUD + checkout, backed by PostgreSQL, calling a downstream **payment-stub** service over HTTP. No React frontend: it adds build complexity without improving the SRE learning; Swagger UI (`/docs`) is our UI.

### 3.2 Hosting decision: **Azure Container Apps (Consumption)** — recommended

| Criterion | Container Apps (chosen) | App Service |
|---|---|---|
| Cost at idle | Consumption plan with monthly free grant; per-second billing | Deployment slots need **Standard S1+** (~$70/mo); Basic has no slots |
| Rollback primitive | **Revisions** + traffic split (free) | Deployment slots (paid tier) |
| Same artifact local ↔ cloud | Yes — the Docker image we test locally | Code deploy differs from local container |
| SRE Agent support | Documented tutorial; Privileged level adds Container Apps Contributor | Documented tutorial |
| Trade-off | Needs a container registry (ACR Basic ~$5/mo) | No registry needed |

### 3.3 Database decision: **Azure Database for PostgreSQL – Flexible Server, Burstable B1ms** — recommended

Why: identical engine locally (`postgres:16` container), pure-Python driver (no ODBC install on Windows), **Microsoft Entra auth with the app's managed identity (no DB password)**, and the server can be **stopped** to create a *real* dependency outage and to save cost.
Alternative: Azure SQL Database free offer — cheaper, but needs the ODBC driver locally and serverless auto-pause produces cold-start latency that muddies latency experiments.

### 3.4 Text architecture diagram

```
                         ┌──────────────────────── GitHub ─────────────────────────┐
                         │ repo: azure-sre-agent-demo (code, docs, runbooks, IaC) │
                         │ Actions ──OIDC (federated cred, no secret)──┐          │
                         └───────────────────────────────▲──────────────┼──────────┘
                                                         │ GitHub connector (read)
 Team (Entra users)                                      │              │ az deployment / az containerapp update
   │ SRE Agent roles                                     │              ▼
   ▼                      ┌──────────── rg-sreagent-demo-agent ───────────────┐
 sre.azure.com ──────────►│ Azure SRE Agent (Microsoft.App/agents)            │
                          │  UAMI ── Reader / Monitoring Reader / LA Reader ──┼──┐ (RG scope)
                          │  custom agents · KB · response plans (Review)     │  │ Monitoring Contributor (sub)
                          └───────────────────────────────────────────────────┘  │
                                                                                 ▼
 ┌──────────────────────────── rg-sreagent-demo-app ──────────────────────────────────────────┐
 │                                                                                             │
 │  Container Apps Environment (Consumption) ── logs ──► Log Analytics workspace ◄── App      │
 │   ├─ ca-orders-api   (FastAPI, OTel, :8000, external HTTPS ingress)          Insights      │
 │   │     │  UAMI id-orders ──► AcrPull, Key Vault Secrets User, PG Entra login (workspace-   │
 │   │     ├──HTTP──► ca-payment-stub (internal ingress only)                    based)        │
 │   │     └──TLS──► PostgreSQL Flexible Server B1ms (Entra auth)                              │
 │   └─ ca-payment-stub                                                                        │
 │  Container Registry (Basic)   Key Vault (RBAC; holds FAULT_ADMIN_TOKEN)                     │
 │  Alert rules (5xx, p95 latency, dependency failures) ─► Action group (email)                │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
 Local: docker compose → orders-api + payment-stub + postgres:16 (no Azure needed)
```

### 3.5 Resources

| Resource | Status | Why |
|---|---|---|
| Resource group ×2 (app, agent) | Essential | Isolates agent scope; app RG is the agent's blast radius |
| Log Analytics workspace (daily cap) | Essential | Single store for app + platform logs; KQL |
| Application Insights (workspace-based) | Essential | Requests/dependencies/exceptions/traces via OpenTelemetry |
| Container Apps environment + 2 apps | Essential | Hosting, revisions for rollback |
| Azure Container Registry (Basic) | Essential for ACA path | Private images pulled by managed identity |
| PostgreSQL Flexible Server B1ms | Essential | Real stateful dependency |
| User-assigned managed identity for app | Essential | No credentials for ACR / KV / DB |
| Key Vault (Standard, RBAC) | Essential (small) | Holds the fault-injection admin token — the one secret we can't eliminate |
| Action group + 3–4 alert rules | Essential (cheap) | Incident signals for the agent |
| Azure SRE Agent | Essential (Day 5+) | The subject of the course |
| Budget + cost alerts | Essential | Notification only; **does not stop spend** |
| Azure Workbook / dashboard | Optional | SLO view; workbooks are free |
| Azure Load Testing, Front Door, APIM, VNet/private endpoints, AKS, Azure OpenAI | **Not needed** | Cost/complexity without learning value here (load test via local script) |

---

## 4. Repository structure (target)

```
azure-sre-agent-demo/
├─ app/                      # orders-api (FastAPI)
│  ├─ main.py  config.py  telemetry.py  logging_setup.py  middleware.py
│  ├─ db.py  models.py  repository.py  payment_client.py
│  ├─ faults.py              # controlled failure injection (off by default, token-protected)
│  └─ routers/  (health.py, orders.py, admin_faults.py)
├─ services/payment_stub/    # tiny downstream dependency
├─ migrations/               # SQL schema + seed
├─ tests/ (unit/, integration/, conftest.py, fixtures/)
├─ scripts/                  # dev.ps1, dev.sh, smoke.ps1, healthcheck.py, load.py, faults.ps1
├─ infra/                    # main.bicep, modules/*.bicep, main.parameters.json, rbac.bicep, alerts.bicep
├─ kql/                      # every query as a .kql file (SLIs, investigations)
├─ docs/                     # ARCHITECTURE … RESOURCE_INVENTORY (Phase 3 list)
├─ runbooks/                 # HIGH_LATENCY, HTTP_5XX_ERRORS, DATABASE_FAILURE, DEPENDENCY_TIMEOUT, RECOVERY_AND_ROLLBACK
├─ agent-context/            # AGENT_INSTRUCTIONS, RESOURCE_BOUNDARIES, custom-agents/*.yaml, response-plans, tests/
├─ api/                      # requests.http + Postman collection
├─ .github/workflows/        # ci.yml (PR), deploy.yml (OIDC, env approval)
├─ .env.example  .gitignore  Dockerfile  docker-compose.yml  pyproject.toml  requirements*.txt
└─ README.md  CONTRIBUTING.md  SECURITY.md  CHECKPOINTS.md
```

---

## 5. 10-day roadmap (agent created on Day 5 to fit the 30-day trial)

| Day | Theme | Key deliverable / gate |
|---|---|---|
| 0 (architect prep) | Prereqs: Azure CLI, Entra account check, sre.azure.com region check, pricing check, budget | §2.3 all ✅ |
| 1 | SRE fundamentals; app walkthrough; run locally | `docker compose up`, all tests green, `/health/ready` = 200 |
| 2 | Fault injection locally; SLI/SLO theory; docs & runbooks | Every fault triggered + recovered locally; SERVICE_LEVELS.md |
| 3 | Bicep provisioning, identity, Key Vault, Postgres Entra auth, deploy | Azure endpoint passes smoke tests |
| 4 | OpenTelemetry → App Insights; KQL fundamentals; alerts; SLO workbook | Queries return data; one alert fires on a test fault |
| 5 | Create SRE Agent (Reader level), connect telemetry + GitHub + KB; Level 1–2 tests | Agent answers L1/L2 with citations |
| 6 | Incident response plan (Review mode), 5xx + latency incidents; L3 | Agent RCA matches injected fault |
| 7 | Custom agents (triage, telemetry, RCA, SLO, remediation, resource analyst); L4–L6 | Handoff chain produces incident report |
| 8 | Permissions matrix, tool policies, hooks, OBO approvals; L7–L8 | Approved revision rollback; denied out-of-scope action |
| 9 | CI/CD with OIDC; L9 adversarial tests; demo rehearsal | Green pipeline; adversarial results logged |
| 10 | Capstone demo + assessment; cleanup decision | Demo recorded; agent deleted or kept consciously |

Rotating roles each day: **App & Deploy**, **Observability & KQL**, **SRE Agent & Incidents**, **Security, Testing & Docs**. Full daily plans come at Phase 11.

---

## 6. Milestones & acceptance criteria (dependency-ordered)

| M | Milestone | Acceptance criteria |
|---|---|---|
| M0 | Prerequisites | Azure CLI ≥ 2.60 logged in; Entra work account confirmed; agent region list non-empty; budget created; providers registered |
| M1 | Local app | `pytest` green; compose healthy; all endpoints return documented codes; JSON logs carry `correlation_id` |
| M2 | Local faults | Each of 7 scenarios observable and reversible; faults disabled by default; admin endpoints 401 without token |
| M3 | Docs & SLOs | Phase 3 docs match code (reviewed by a 2nd person); SLO table with numerator/denominator |
| M4 | Azure infra | `az deployment group what-if` clean; deploy succeeds; no secrets in outputs |
| M5 | Azure app | Public HTTPS endpoint; `/health/ready` 200; smoke test passes; DB via managed identity |
| M6 | Telemetry | AppRequests/AppDependencies/AppExceptions populated; SLI queries return values; alert fires on test |
| M7 | Agent baseline | Agent created at Reader level on app RG; L1–L2 tests pass |
| M8 | Incidents | Response plan in **Review**; L3–L5 pass |
| M9 | Multi-agent | Custom agents + handoffs; L6 pass |
| M10 | Remediation & governance | Approved write succeeds via approval/OBO; L7–L9 pass |
| M11 | CI/CD | PR workflow + OIDC deploy with environment approval |
| M12 | Capstone & cleanup | Demo script executed; cleanup checklist done |

---

## 7. Initial cost & security checklist

**Cost**
- [ ] Check `$/AAU` and region prices in the [pricing calculator](https://azure.microsoft.com/pricing/calculator/)
- [ ] Budget on the subscription (e.g. USD 100/month, alerts at 50/80/100 %) — notification only
- [ ] Log Analytics daily cap (e.g. 0.5 GB/day) and 30-day retention
- [ ] Postgres B1ms stopped outside training hours (auto-restarts after 7 days — re-stop)
- [ ] Container Apps `minReplicas` 1 only during sessions, 0 otherwise
- [ ] SRE Agent created on Day 5, active-flow cap 500 AAU, **deleted before trial day 30** (or keep consciously)
- [ ] Tags on everything: `Project=AzureSREAgentDemo, Environment=NonProduction, Owner=Team, AutoCleanup=ReviewRequired`

Rough monthly infra estimate **excluding the agent** (illustrative, verify in calculator): ACA ≈ $5–25, Postgres B1ms + 32 GB ≈ $15–20, ACR Basic ≈ $5, Log Analytics ≈ $0–10 (first 5 GB/month free per billing account), Key Vault/alerts ≈ $1–3 → **≈ $30–60/month**, much less if stopped between sessions.
Agent after trial: 2,920 AAU/month always-on × your `$/AAU` + active flow.

**Security**
- [ ] No secrets in git (`.env` git-ignored; `gitleaks` in CI)
- [ ] App → ACR/KV/Postgres via managed identity; Postgres Entra-only auth
- [ ] Fault endpoints: disabled unless `FAULTS_ENABLED=true` **and** `X-Fault-Token` matches Key Vault secret
- [ ] Agent at **Reader** level on the app RG only; never Owner; no subscription-wide Contributor
- [ ] Response plans in **Review** (override the Autonomous default)
- [ ] GitHub Actions uses OIDC federated credential scoped to the app RG; `production` environment requires reviewer
- [ ] MFA on all human accounts; SRE Agent Administrator limited to the architect (+1 backup)

---

## 8. Open items to verify (tracked in CHECKPOINTS.md)

1. `$/AAU` in chosen region.
2. Whether your sign-in is an Entra work account (OBO requirement).
3. Knowledge-base location and file limits in the current UI.
4. Which built-in specialist agents currently ship in Agent Canvas.
5. Exact Log Analytics table names produced by our OTel config (AppRequests vs requests) — verified at M6.
6. Model providers offered for our subscription/region.
