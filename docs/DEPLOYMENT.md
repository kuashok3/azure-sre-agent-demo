# Deployment

## 1. Local [LIVE-LOCAL]

See [../README.md](../README.md) Steps 1–8. Startup order: `postgres` (healthy) → `migrate` (exit 0)
→ `payment-stub` → `orders-api`. Code rollback: `git checkout <commit>` then `docker compose up -d --build`.

---

## 2. Azure (M4 infrastructure + M5 application)

> **Status:** templates compile and pass `az bicep lint`; region availability was checked for
> eastus2 and centralindia (2026-10-12). **eastus2 refused Burstable PostgreSQL (B1ms and B2s,
> `SkuNotAvailable`) for this subscription**; a probe server in **centralindia succeeded** (2026-10-13),
> so the stack runs in centralindia. This section becomes [VERIFIED] after the first successful run.
>
> **Moving from a failed region?** Follow "Region move" in §5 first.
>
> Shell: **Windows PowerShell**, from the repo root. Run steps in order, in **one** window: later steps
> reuse variables from Step 1. If you open a new window, re-run Step 1.

### What gets created

| Phase | Resources | Rough cost |
|---|---|---|
| Budget | `budget-sredemo` (subscription, filtered by tag `Project=AzureSREAgentDemo`) | free |
| Phase 1 | Log Analytics (0.5 GB/day cap), App Insights, managed identity, ACR Basic, Key Vault, PostgreSQL B1ms (Entra-only auth), Container Apps environment | PostgreSQL + ACR run 24×7 until stopped or deleted |
| Phase 2 | `ca-payment-stub` (internal) and `ca-orders-api` (public HTTPS), 1 replica each | per-second while running |

---

### Step 1: Session variables
**Objective:** define names once so every command uses the same values.
```powershell
cd C:\Users\Relanto\Desktop\Azure_SRE
az account show --query "{subscription:name, user:user.name}" -o table   # confirm the right subscription
$LOCATION = "centralindia"       # eastus2 refused cheap PostgreSQL for this subscription (2026-10-13)
$RG       = "rg-sredemo-app"
$ME_ID    = az ad signed-in-user show --query id -o tsv
$ME_UPN   = az ad signed-in-user show --query userPrincipalName -o tsv
$MY_IP    = (Invoke-RestMethod https://api.ipify.org)
$TAG      = git rev-parse --short HEAD
$PG_SKU   = "Standard_B1ms"  # probe-tested OK in centralindia on 2026-10-13
"$LOCATION | $RG | $PG_SKU | $ME_UPN | $MY_IP | image tag $TAG"
```
**Expected:** one line with all values filled in. **Why `$MY_IP`:** the PostgreSQL firewall allows
only Azure services plus your current IP (needed to run migrations in Step 9). If your IP changes,
re-run Step 5 with the new value.

### Step 2: Resource group with tags
**Why:** the resource group is the cleanup and permission boundary. The SRE Agent will only see this group.
```powershell
az group create --name $RG --location $LOCATION --tags Project=AzureSREAgentDemo Environment=NonProduction Owner=Team AutoCleanup=ReviewRequired -o table
```
**Expected:** `ProvisioningState Succeeded`.

### Step 3: Project budget (USD 50/month, e-mail alerts at 50/80/100% and forecast 100%)
```powershell
az deployment sub create --name budget-sredemo --location $LOCATION --template-file infra/budget.bicep --parameters amount=50 contactEmail=$ME_UPN -o table
az consumption budget list --query "[].{name:name, amount:amount}" -o table --only-show-errors
```
**Expected:** `budget-sredemo 50.0` next to the existing `dev_env_monthly_budget`.
**Remember:** budgets only send e-mails, cost data lags by up to 24 h, and only tagged resources count.

### Step 4: Preview (what-if): nothing is created yet
```powershell
az deployment group what-if -g $RG -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU
```
**Expected:** a list of `+ Create` items (≈ 15 resources/role assignments), **no** `- Delete` and no
changes outside `rg-sredemo-app`. Stop here if anything looks wrong.

### Step 5: Deploy phase 1 (infrastructure): about 10–15 minutes, PostgreSQL is the slowest
```powershell
az deployment group create -g $RG -n phase1 -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU -o table
$OUT = az deployment group show -g $RG -n phase1 --query properties.outputs -o json | ConvertFrom-Json
$ACR = $OUT.registryName.value; $KV = $OUT.keyVaultName.value; $PG = $OUT.postgresServerName.value; $PG_FQDN = $OUT.postgresFqdn.value
"$ACR | $KV | $PG | $PG_FQDN"
```
**Validation:** `az resource list -g $RG --query "[].{name:name, type:type}" -o table` lists the
workspace, App Insights, identity, registry, vault, PostgreSQL server and environment.

> **Opened a new PowerShell window after Step 5?** Re-run Step 1, then reload the names:
> ```powershell
> $OUT = az deployment group show -g $RG -n phase1 --query properties.outputs -o json | ConvertFrom-Json
> $ACR = $OUT.registryName.value; $KV = $OUT.keyVaultName.value; $PG = $OUT.postgresServerName.value; $PG_FQDN = $OUT.postgresFqdn.value
> ```

### Step 6: Fault-admin token into Key Vault (generated locally, never displayed)
```powershell
$bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$TOKEN = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
az keyvault secret set --vault-name $KV --name fault-admin-token --value $TOKEN --output none
Remove-Variable TOKEN, bytes
az keyvault secret show --vault-name $KV --name fault-admin-token --query "attributes.enabled" -o tsv
```
**Expected:** `true`. **If `Forbidden`:** your new *Key Vault Secrets Officer* role can take 1–5 minutes
to apply. Wait, then re-run the `secret set` line (regenerate the token first).

### Step 7: Build the image in Azure (no local push needed)
```powershell
az acr build --registry $ACR --image "sre-demo-app:$TAG" --build-arg APP_VERSION=$TAG --build-arg GIT_SHA=$TAG .
az acr repository show-tags --name $ACR --repository sre-demo-app -o table
```
**Expected:** the build log ends with `Run ID: ... was successful`, and the tag is listed.
`.dockerignore` keeps `.env` and `.venv` out of the upload.
**If ACR Tasks are not allowed on the subscription**, use local Docker instead:
`az acr login -n $ACR; docker build -t "$ACR.azurecr.io/sre-demo-app:$TAG" --build-arg APP_VERSION=$TAG --build-arg GIT_SHA=$TAG .; docker push "$ACR.azurecr.io/sre-demo-app:$TAG"`

### Step 8: (no command) Why the database step is separate
Password login is **disabled** on the server. Only Microsoft Entra identities can sign in: you (admin)
and the app's managed identity. Bicep can't create database users inside PostgreSQL, so you do it once,
as admin, in Step 9.

### Step 9: Migrations + app database role (least privilege)
```powershell
.\.venv\Scripts\python.exe scripts\azure_db_bootstrap.py --server-fqdn $PG_FQDN --admin-upn $ME_UPN
```
**Expected:** `[1/3] migrations applied ... ['001_create_orders.sql']`, `[2/3] created Entra role 'id-orders-api'`,
`[3/3] granted data-only access ...`. Re-running is safe.

### Step 10: Deploy phase 2 (apps)
```powershell
az deployment group create -g $RG -n phase2 -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU deployApps=true imageTag=$TAG gitSha=$TAG -o table
$FQDN = az deployment group show -g $RG -n phase2 --query properties.outputs.ordersAppFqdn.value -o tsv
$URL = "https://$FQDN"; $URL
```

### Step 11: Post-deployment checks (M5 acceptance)
```powershell
curl.exe -s "$URL/health/ready"
python scripts\smoke_test.py --base-url $URL
```
**Expected:** readiness `{"status":"ready",...}` with database and payment_service `ok`;
`ALL CHECKS PASSED`. The first request after a deploy can take a few seconds (container start).

### Step 12: Fault drills in Azure
```powershell
$env:FAULT_ADMIN_TOKEN = az keyvault secret show --vault-name $KV --name fault-admin-token --query value -o tsv
python scripts\fault.py list --base-url $URL
python scripts\validate_faults.py --base-url $URL
Remove-Item Env:FAULT_ADMIN_TOKEN
```
**Expected:** `ALL SCENARIOS PASSED` (synthetic faults; `--include-docker` does not apply in Azure).

### Step 13: Telemetry arrives (quick check; deep validation is M6)
Azure portal → `appi-sredemo` → **Logs** → run `requests | take 10`. Data appears 2–5 minutes after traffic.

### Step 14: Rollback rehearsal
```powershell
az acr build --registry $ACR --image "sre-demo-app:$TAG-v2" --build-arg APP_VERSION="$TAG-v2" --build-arg GIT_SHA=$TAG .
az deployment group create -g $RG -n phase2-v2 -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU deployApps=true imageTag="$TAG-v2" gitSha=$TAG -o none
curl.exe -s "$URL/info"          # version = <tag>-v2
# Roll back = redeploy the previous tag
az deployment group create -g $RG -n phase2-rollback -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU deployApps=true imageTag=$TAG gitSha=$TAG -o none
curl.exe -s "$URL/info"          # version = <tag>
az containerapp revision list -n ca-orders-api -g $RG --query "[].{name:name, active:properties.active, created:properties.createdTime}" -o table
```

---

## 3. Daily cost routine

| When | Command | Effect |
|---|---|---|
| End of day | `az postgres flexible-server stop -g $RG -n $PG` | Stops DB compute billing (storage still billed). **The app then returns 503**, which is also a real-outage drill |
| End of day | `az containerapp update -n ca-orders-api -g $RG --min-replicas 0` (same for `ca-payment-stub`) | Scale to zero |
| Start of day | `az postgres flexible-server start -g $RG -n $PG`, then re-run Step 10 | Restores 1 replica each |

PostgreSQL restarts itself after 7 days stopped. Re-stop it if the project is paused longer.

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `what-if`/`create` fails with `AuthorizationFailed` on role assignments | Account lacks Owner / User Access Administrator | Use the Owner account |
| PostgreSQL `SkuNotAvailable` (seen 2026-10-13 for B1ms in eastus2) | Size not offered to this subscription in the region, even though `list-skus` shows it | Set `$PG_SKU = "Standard_B2s"` and re-run Step 5 (other resources are kept) |
| PostgreSQL `LocationIsOfferRestricted` / quota error | Region capacity for the subscription | Re-run Step 1 with the other region (new RG name) |
| `ServerIsBusy` / conflicting operation on PostgreSQL | Child resources changed concurrently | Re-run Step 5. It's idempotent |
| Step 5 re-run fails while the server is stopped | Updates need a running server | `az postgres flexible-server start ...` first |
| Step 9 `password authentication failed` / timeout | Firewall IP changed, or not logged in | Update `$MY_IP` and re-run Step 5; `az login` |
| Step 9 `pgaadauth_create_principal` error | You're not the Entra admin, or the identity name differs | Check `az postgres flexible-server ad-admin list -g $RG -s $PG -o table` |
| Revision `Failed`, `secret ... key vault` error | Secret missing, or the identity lacks Secrets User | Do Step 6; wait for role propagation; re-run Step 10 |
| Revision `Failed`, image pull error | Tag not in ACR, or AcrPull not yet active | `az acr repository show-tags ...`; wait and re-run Step 10 |
| Readiness 503 `database_unavailable` | DB role/grants missing, or server stopped | Step 9; check the server state |
| Checkout 503 `payment_service_unavailable` | payment-stub down or the URL wrong | `az containerapp revision list -n ca-payment-stub -g $RG -o table` |
| No telemetry | Wrong connection string, or ingestion delay | Wait 5 min; `/info` shows `telemetry_enabled: true`? |

## 5. Region move (start over cleanly in another region)

Use this when a region refuses a resource and you want to rebuild elsewhere. Resource names come from
the resource group name, so the **same names** are reused in the new region. Two resource types keep
deleted names reserved (Key Vault soft-delete; Log Analytics 14-day recovery), so release them first.

```powershell
$OLD_LOCATION = "eastus2"
# 1. Permanently delete the workspace (otherwise its name stays reserved for 14 days)
az monitor log-analytics workspace delete -g rg-sredemo-app -n log-sredemo --force true --yes
# 2. Delete the resource group and everything in it (~5 min; waits until done)
az group delete --name rg-sredemo-app --yes
# 3. Release the Key Vault name (it is soft-deleted, not gone)
az keyvault list-deleted --query "[].{name:name, location:properties.location}" -o table
az keyvault purge --name kv-sredemo-uuouh --location $OLD_LOCATION
# 4. Confirm the clean slate
az group exists --name rg-sredemo-app          # false
```
Then run **Step 1** (new `$LOCATION`), **Step 2**, **Step 4**, **Step 5**. The budget (Step 3) is
subscription-wide and stays as it is.
