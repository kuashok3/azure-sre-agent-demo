# Permission Matrix

> **Verified 2026-10-13** with `az role assignment list` after creating the SRE Agent and removing the
> auto-granted Container Apps Operator role. Re-verify after any change in the SRE Agent portal:
> re-adding a resource group there re-applies its default roles.

## Who is who (five kinds of identity)

| Identity | What it is | Used for |
|---|---|---|
| **Architect** `ashok.kumar@relanto.ai` | Human, Microsoft Entra work account | Builds and administers; the only approver of agent write actions |
| **App identity** `id-orders-api` | User-assigned managed identity (rg-sredemo-app) | The running apps pull images, read one Key Vault secret, sign in to PostgreSQL |
| **Agent identity** `sre-sredemo-6cer2nfan6xxa` | User-assigned managed identity created by the agent wizard (rg-sredemo-agent) | The SRE Agent reads resources and telemetry |
| **Agent system identity** | System-assigned identity on the agent | Agent infrastructure (no role assignments) |
| **GitHub identity** | `kuashok3` (OAuth for the agent's code connector); OIDC app for CI/CD (M11) | Read repo; deploy (later) |

## Azure RBAC (actual)

| Principal | Role | Scope | Why |
|---|---|---|---|
| Architect | Owner (subscription; pre-existing) | Bangalore Azure PayAsYouGo | Build everything |
| Architect | **SRE Agent Administrator** | `sre-sredemo` | Chat, configure, **approve actions**, OBO elevation |
| Architect | Key Vault Secrets Officer | `kv-sredemo-uuouh` | Store the fault token |
| Architect | PostgreSQL Entra admin | `psql-sredemo-uuouh` | Migrations, create the app DB role |
| `id-orders-api` | AcrPull | `crsredemouuouh` | Pull the image |
| `id-orders-api` | Key Vault Secrets User | `kv-sredemo-uuouh` | Read `fault-admin-token` |
| `id-orders-api` | PostgreSQL role: SELECT/INSERT/UPDATE/DELETE only (no TRUNCATE, no DDL) | database `orders` | Run the business logic |
| Agent identity | Reader | `rg-sredemo-app` | See resources and configuration |
| Agent identity | Monitoring Reader | `rg-sredemo-app` | Metrics, alerts (read) |
| Agent identity | Log Analytics Reader | `rg-sredemo-app` | KQL on `log-sredemo` |
| Agent identity | Monitoring Contributor | `rg-sredemo-agent` (its own group only) | Agent's own monitoring resources |
| Agent identity | ~~Container Apps Operator~~ **removed** | ~~rg-sredemo-app~~ | Auto-granted at "Reader" level; included `containerApps/exec` (shell into the app, so it could use the app's identity and secrets), `listSecrets` and restart actions |
| Agent identity | **nothing** at subscription scope | — | Shared subscription with other teams (CHECKPOINTS issues 14, 15) |

## What this means in practice

| Agent wants to... | Allowed? | How |
|---|---|---|
| Query logs/metrics, read resource config, read code and docs | Yes | Own identity |
| Restart a revision, roll back, scale, start PostgreSQL | **Only with approval** | Agent asks; architect authorizes via on-behalf-of (OBO) for that one action |
| Read secrets, exec into containers, change RBAC, delete anything | No | No role grants it; also prohibited in `agent-context/RESOURCE_BOUNDARIES.md` |
| Act on other teams' resources | No | No role outside our two resource groups |
| Acknowledge/close Azure Monitor alerts | Not yet | Needs subscription-scope Monitoring Contributor, decision in M8 (issue 15) |

## SRE Agent user roles (planned for the team)

| Person | SRE Agent role |
|---|---|
| Architect | Administrator ✅ |
| Backup approver (one teammate) | Administrator (to add) |
| Other teammates | Standard User (+ Author when building custom agents in M9) |

Owner/Contributor on Azure do **not** grant SRE Agent chat or approval rights; these roles are separate.
