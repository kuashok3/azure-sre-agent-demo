# Cost Management

> Estimates are **illustrative**. Confirm in the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/)
> for your region before provisioning (M4). **A budget only notifies; it never stops spending.**

## Cost drivers

| Resource | Billing model | Charged when idle? | Rough monthly (USD) | Control |
|---|---|---|---|---|
| Azure SRE Agent: always-on | 4 AAU per agent-hour (≈ 2,920 AAU/month) | **Yes, until deleted** (stopping does not help) | 2,920 × $/AAU (**$/AAU unverified**) | Create on Day 5; 30-day trial waives it; **delete** when done |
| Azure SRE Agent: active flow | Tokens → AAU (≈ 1–4 AAU per question, 12–35 per investigation) | No | depends on use | Monthly cap ≥ 500 AAU in Settings › Agent consumption |
| PostgreSQL Flexible B1ms + 32 GB storage | per hour + storage | Compute yes unless **stopped**; storage always | ~$15–20 | `az postgres flexible-server stop` between sessions (auto-starts after 7 days) |
| Container Apps (Consumption) | vCPU-s, GiB-s, requests; monthly free grant | Yes if `minReplicas ≥ 1` | ~$5–25 | `minReplicas 0` outside sessions |
| Container Registry Basic | per day | Yes | ~$5 | Delete with the RG |
| Log Analytics / App Insights | per GB ingested (first 5 GB/month free per billing account) + retention | Only what is ingested | ~$0–10 | Daily cap, 30-day retention, `/health/live` excluded from telemetry |
| Key Vault, alert rules, action group | per operation / per rule | Rules yes (small) | ~$1–3 | Few rules |

## Controls checklist
- [ ] Subscription budget (for example USD 100/month) with alerts at 50/80/100% to the architect.
- [ ] Tags on all resources: `Project=AzureSREAgentDemo`, `Environment=NonProduction`, `Owner=Team`, `AutoCleanup=ReviewRequired`.
- [ ] Log Analytics daily cap set.
- [ ] End-of-day routine: stop PostgreSQL, scale apps to 0 (commands in M4).
- [ ] Trial end date for the SRE Agent written in the team calendar (creation date + 30 days).
- [ ] Weekly check of Cost Management › Cost analysis, filtered by tag `Project`.

## Cleanup (end of project)
1. Delete the SRE Agent (sre.azure.com › Settings › Basics › Delete), or delete `rg-sredemo-agent`.
2. `az group delete --name rg-sredemo-app` removes the app, database, registry, Key Vault and telemetry.
3. Key Vault **soft-delete**: the vault name stays reserved for the retention period. Purge only if you are sure.
4. Check that nothing tagged `Project=AzureSREAgentDemo` remains:
   `az resource list --tag Project=AzureSREAgentDemo -o table`.
5. Remove role assignments and the GitHub OIDC app registration created for CI.
