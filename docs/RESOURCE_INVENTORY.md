# Resource Inventory

> Subscription: **Bangalore Azure PayAsYouGo** (shared with other teams; see CHECKPOINTS issue 14).
> Region: **centralindia** (eastus2 refused Burstable PostgreSQL for this subscription on 2026-10-13).
> Name suffix: **`uuouh`** (derived from the resource group ID; stable across re-deployments).

All resources carry tags: `Project=AzureSREAgentDemo`, `Environment=NonProduction`, `Owner=Team`,
`AutoCleanup=ReviewRequired`.

| Resource | Name | Type | Status |
|---|---|---|---|
| Project budget | `budget-sredemo` (USD 50/month, tag-filtered) | Microsoft.Consumption/budgets (subscription) | ✅ created 2026-10-12 |
| App resource group | `rg-sredemo-app` | Resource group | ✅ centralindia |
| Log Analytics workspace | `log-sredemo` (30-day retention, 0.5 GB/day cap) | Microsoft.OperationalInsights/workspaces | ✅ phase 1 |
| Application Insights | `appi-sredemo` (workspace-based) | Microsoft.Insights/components | ✅ phase 1 |
| App managed identity | `id-orders-api` | Microsoft.ManagedIdentity/userAssignedIdentities | ✅ phase 1 |
| Container registry | `crsredemouuouh` (Basic, admin user off) | Microsoft.ContainerRegistry/registries | ✅ phase 1 |
| Key Vault | `kv-sredemo-uuouh` (RBAC, soft-delete 7 days) | Microsoft.KeyVault/vaults | ✅ phase 1 |
| PostgreSQL server | `psql-sredemo-uuouh` (B1ms, v16, Entra-only) + database `orders` | Microsoft.DBforPostgreSQL/flexibleServers | ✅ phase 1, state Ready |
| Container Apps environment | `cae-sredemo` | Microsoft.App/managedEnvironments | ✅ phase 1 |
| orders-api | `ca-orders-api` | Microsoft.App/containerApps | ⬜ phase 2 (M5) |
| payment-stub | `ca-payment-stub` | Microsoft.App/containerApps | ⬜ phase 2 (M5) |
| Action group | `ag-sredemo` (e-mail ashok.kumar@relanto.ai) | Microsoft.Insights/actionGroups | ⏳ M6 Step 15 |
| Alert rules | `alert-sredemo-5xx-rate`, `-latency-p95`, `-dependency-failures`, `-database-unavailable` | Microsoft.Insights/scheduledQueryRules | ⏳ M6 Step 15 |
| Agent resource group | `rg-sredemo-agent` | Resource group | ⬜ Day 5 (M7) |
| Azure SRE Agent | `sre-sredemo` | Microsoft.App/agents | ⬜ Day 5 (M7) |

## Role assignments created by phase 1

| Principal | Role | Scope |
|---|---|---|
| `id-orders-api` | AcrPull | `crsredemouuouh` |
| `id-orders-api` | Key Vault Secrets User | `kv-sredemo-uuouh` |
| Architect (ashok.kumar@relanto.ai) | Key Vault Secrets Officer | `kv-sredemo-uuouh` |
| Architect | PostgreSQL Microsoft Entra administrator | `psql-sredemo-uuouh` |

## Network rules

| Resource | Rule |
|---|---|
| `psql-sredemo-uuouh` | `AllowAzureServices` (0.0.0.0) + `AllowDeployerIp` (architect's IP at deploy time) |

**Out of scope:** every other resource group and resource in the subscription. See
[../agent-context/RESOURCE_BOUNDARIES.md](../agent-context/RESOURCE_BOUNDARIES.md).
