# Deployment

## 1. Local [LIVE-LOCAL]

See [../README.md](../README.md) Steps 1–8. Summary:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
docker compose up -d --build
python scripts\smoke_test.py
```

Order of startup: `postgres` (healthy) → `migrate` (exit 0) → `payment-stub` → `orders-api`.

### Rollback locally
Code is versioned in git: `git checkout <previous-commit>`, then `docker compose up -d --build`.
Data: `docker compose down -v` wipes the database (migrations re-run on the next start).

## 2. Azure [PLANNED-AZURE: written in full during M4/M5]

Planned sequence (each step will get exact, tested commands):

1. Select subscription and region (`eastus2`); create `rg-sredemo-app` with tags.
2. Deploy `infra/main.bicep`: Log Analytics, App Insights, ACR, Key Vault, managed identity,
   PostgreSQL Flexible Server (Entra auth), Container Apps environment.
3. Store `FAULT_ADMIN_TOKEN` in Key Vault (generated, never typed into chat or committed).
4. Build and push the image to ACR (`az acr build`, no local Docker push credentials needed).
5. Create the managed identity's PostgreSQL role; run migrations.
6. Deploy `ca-payment-stub` (internal) and `ca-orders-api` (external) referencing the image by tag.
7. Post-deployment checks: `smoke_test.py --base-url https://<fqdn>`, telemetry visible in App Insights.
8. Rollback test: activate the previous revision / shift traffic, then verify.

Acceptance criteria are in [00_PHASE0_BLUEPRINT.md](00_PHASE0_BLUEPRINT.md) §6 (M4, M5).
