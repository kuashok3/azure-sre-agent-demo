# Resource Inventory

> **Status: PLANNED.** Nothing is deployed in Azure yet. Names are confirmed in M4, and this file is
> updated with real resource IDs then. `<suffix>` = 4–5 lowercase characters for globally unique names.

All resources carry tags: `Project=AzureSREAgentDemo`, `Environment=NonProduction`, `Owner=Team`,
`AutoCleanup=ReviewRequired`.

| Resource | Planned name | Type | RG | Agent can see? | Status |
|---|---|---|---|---|---|
| App resource group | `rg-sredemo-app` | Resource group | — | Yes (managed scope) | planned |
| Agent resource group | `rg-sredemo-agent` | Resource group | — | n/a | planned (Day 5) |
| Log Analytics workspace | `log-sredemo` | Microsoft.OperationalInsights/workspaces | app | Yes | planned |
| Application Insights | `appi-sredemo` | Microsoft.Insights/components | app | Yes | planned |
| Container Apps environment | `cae-sredemo` | Microsoft.App/managedEnvironments | app | Yes | planned |
| orders-api | `ca-orders-api` | Microsoft.App/containerApps | app | Yes | planned |
| payment-stub | `ca-payment-stub` | Microsoft.App/containerApps | app | Yes | planned |
| Container registry | `crsredemo<suffix>` | Microsoft.ContainerRegistry/registries | app | Yes | planned |
| Key Vault | `kv-sredemo-<suffix>` | Microsoft.KeyVault/vaults | app | metadata only (no secret read) | planned |
| PostgreSQL server | `psql-sredemo-<suffix>` | Microsoft.DBforPostgreSQL/flexibleServers | app | Yes | planned |
| App managed identity | `id-orders-api` | Microsoft.ManagedIdentity/userAssignedIdentities | app | Yes | planned |
| Action group | `ag-sredemo` | Microsoft.Insights/actionGroups | app | Yes | planned (M6) |
| Alert rules | `alert-sredemo-*` | Microsoft.Insights/scheduledQueryRules | app | Yes | planned (M6) |
| Azure SRE Agent | `sre-sredemo` | Microsoft.App/agents | agent | — | planned (Day 5) |
| Agent identity | auto-created UAMI | Microsoft.ManagedIdentity/userAssignedIdentities | agent | — | planned (Day 5) |

**Out of scope:** every other resource group and resource in the subscription. See
[../agent-context/RESOURCE_BOUNDARIES.md](../agent-context/RESOURCE_BOUNDARIES.md).
