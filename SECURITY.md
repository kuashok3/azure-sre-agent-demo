# Security

This is a **non-production training project**. Even so, we follow production habits.

## Secrets
- Never commit `.env`, connection strings, tokens or keys. `.gitignore` excludes `.env`.
- `.env.example` contains **local-only placeholder values**; they are rejected in Azure
  (`ENVIRONMENT=azure` refuses the `change-me…` fault token).
- In Azure, the app authenticates to the container registry, Key Vault and PostgreSQL with a
  **managed identity**. There is no database password. The only secret, `FAULT_ADMIN_TOKEN`,
  lives in Key Vault.

## Fault-injection API (`/admin/faults`)
It can deliberately break the service, so:
- it is **not mounted at all** unless `FAULTS_ENABLED=true` (then the URLs return 404);
- every call needs the `X-Fault-Token` header (≥ 16 characters, compared in constant time);
- every change is logged at WARNING level (`event=fault_enabled|fault_disabled|faults_reset`);
- fault state is in memory only and clears on restart;
- payment-stub's admin API is only reachable inside the Container Apps environment.

Never enable it against an environment that real users depend on.

## Least privilege
- The Azure SRE Agent starts at **Reader** permission level on the app resource group only.
- Write actions require SRE Agent Administrator approval (Review run mode).
- See `docs/00_PHASE0_BLUEPRINT.md` §2.4 and the permission matrix (added in Phase 6).

## Reporting a problem
Raise it with the project architect directly; do not open a public issue containing secrets.
