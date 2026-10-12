# Runbook: Recovery and Rollback

Choose the **least risky reversible** action that addresses the verified cause.

## Order of preference
1. **Remove the trigger**: reset drill faults; revert a config change.
2. **Roll back**: route traffic to the previous healthy revision.
3. **Restart**: restart the revision (clears in-memory state, including fault state).
4. **Scale**: add replicas (only for capacity problems; cost).
5. **Start a stopped dependency**: e.g. the PostgreSQL server.

Never "recover" by silencing alerts, disabling health checks or raising timeouts.

## Local
```powershell
python scripts\fault.py reset
docker compose restart orders-api
git checkout <good-commit>; docker compose up -d --build     # code rollback
```

## Azure [PLANNED-AZURE: exact revision mode decided and tested in M4/M5]

```powershell
# List revisions with health and traffic
az containerapp revision list -n ca-orders-api -g rg-sredemo-app `
  --query "[].{name:name, active:properties.active, traffic:properties.trafficWeight, health:properties.healthState, created:properties.createdTime}" -o table

# Multiple-revision mode: send 100% of traffic to the previous good revision
az containerapp ingress traffic set -n ca-orders-api -g rg-sredemo-app --revision-weight <good-revision>=100

# Single-revision mode: redeploy the previous image tag
az containerapp update -n ca-orders-api -g rg-sredemo-app --image <acr>.azurecr.io/sre-demo-app:<previous-tag>

# Restart a revision
az containerapp revision restart -n ca-orders-api -g rg-sredemo-app --revision <revision>
```

| Action | Approval | Verify with |
|---|---|---|
| Fault reset | Human operator | `fault.py list` → none |
| Traffic shift / image rollback | **SRE Agent Administrator or human operator** | revision health `Healthy`, smoke test |
| Restart | **Required** | readiness, error rate |
| Scale 1–3 replicas | **Required** | replica count, latency |

## Recovery verification checklist (always)
- [ ] `/health/ready` → 200 `ready`
- [ ] `python scripts/smoke_test.py --base-url <url>` → ALL CHECKS PASSED
- [ ] 5xx < 0.5% and p95 under threshold for ≥ 10 minutes (KQL in SERVICE_LEVELS)
- [ ] No active faults
- [ ] Alert resolved by itself (not manually silenced)
- [ ] Incident timeline and budget impact recorded
