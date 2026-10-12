# Runbook: Database Failure

**Use when:** `503 database_unavailable`, `/health/ready` 503 with `checks.database.status = error`,
or `postgresql` dependency failures. **Related:** FM-3, FM-4.

## 1. Confirm
```powershell
curl.exe -s https://<orders-fqdn>/health/ready     # local: http://localhost:8080/health/ready
```
```kusto
AppDependencies
| where TimeGenerated > ago(30m) and AppRoleName == "orders-api" and DependencyType == "postgresql"
| summarize calls = count(), failed = countif(Success == false), p95 = percentile(DurationMs, 95) by bin(TimeGenerated, 5m)
```

## 2. Synthetic or real?
| Evidence | Synthetic (`db_connection_failure`) | Real outage |
|---|---|---|
| Error message | `... (injected fault: db_connection_failure)` | `Database unavailable (OperationalError)` or `(PoolTimeout)` |
| Audit log | `event=fault_enabled`, `fault_name=db_connection_failure` | none |
| `psycopg.pool` warnings | no | yes, repeated connection errors |
| Server state | `Ready` | `Stopped`, `Updating`, or `is_db_alive` = 0 |

```powershell
# [PLANNED-AZURE]
az postgres flexible-server show -g rg-sredemo-app -n psql-sredemo-<suffix> --query "{state:state, version:version, sku:sku.name}" -o table
```
Local: `docker compose ps postgres`.

## 3. Real-outage causes to check
1. Server **stopped** (manual stop, or cost routine) → start it.
2. Maintenance/restart in progress → wait and watch.
3. Authentication: Entra token or role missing for `id-orders-api` (look for auth errors in logs).
4. Firewall/network change.
5. Connection exhaustion: pool max 5 per replica. Check server connection metrics.

## 4. Mitigations

| Action | Command | Approval |
|---|---|---|
| Reset drill fault | `python scripts/fault.py reset` | Human operator |
| Start a stopped server | `az postgres flexible-server start -g rg-sredemo-app -n psql-sredemo-<suffix>` (local: `docker compose start postgres`) | **Required** |
| Restart the app | not needed: the pool reconnects on its own (verified locally) | — |
| Stop/delete server, change firewall, reset admin | — | **Prohibited for the agent** |

## 5. Verify
Readiness 200 `ready`, `postgresql` dependency failures 0 for 10 min, smoke test passes.
Orders created during the outage were rejected (503), never half-written: the insert is transactional.

## Prompts for Azure SRE Agent
- "orders-api readiness reports the database as down. Is the PostgreSQL server itself unhealthy or stopped, or is this an application-side/injected failure? Show the evidence for each possibility."
