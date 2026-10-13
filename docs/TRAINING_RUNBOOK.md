# Training Runbook: From Code to Azure SRE Agent (hands-on, 5 people)

**Format:** the facilitator runs each step on screen, explains it, then every developer runs the same
step in their **own** environment. Do not move to the next step until everyone hits the ✅ checkpoint.

**Everyone works in the same Azure subscription** (`Bangalore Azure PayAsYouGo`, shared with other
teams). Each person picks an **alias**, and every resource name is derived from it, so nobody collides with
anybody else, and nobody touches other teams' resources.

| | Facilitator (already built) | Each developer |
|---|---|---|
| App resource group | `rg-sredemo-app` | `rg-sredemo-<alias>` |
| Agent resource group | `rg-sredemo-agent` | `rg-sredemo-<alias>-agent` |
| SRE Agent | `sre-sredemo` | `sre-<alias>` |
| Registry / Key Vault / PostgreSQL | auto-suffixed, globally unique | auto-suffixed, globally unique |

**Shell:** Windows PowerShell for everything. Keep **one** window open all day: later steps reuse the
variables set earlier. If a window is closed, re-run **Step 4.1** and **Step 5.0**.

**Region:** `centralindia`. (`eastus2` refused cheap PostgreSQL for this subscription, so don't change it.)

| Module | Topic | Time |
|---|---|---|
| 0 | Facilitator prep (day before) | — |
| 1 | Tools on every laptop | 30 min |
| 2 | Get the code, run it locally | 30 min |
| 3 | Break it locally: failure scenarios | 30 min |
| 4 | Azure foundation (infrastructure) | 45 min (15 min of waiting is a theory slot) |
| 5 | Application in Azure | 45 min |
| 6 | Observability: KQL + alerts | 40 min |
| 7 | Create your SRE Agent | 40 min |
| 8 | Test the agent (Level 1–2) | 40 min |
| 9 | Incident exercise with the agent | 45–60 min |
| 10 | Cost routine and cleanup | 15 min |
| A | Troubleshooting (errors we really hit) | — |

---

## Module 0: Facilitator prep (do the day before)

| # | Task | How | Why |
|---|---|---|---|
| 0.1 | Give everyone repo access | GitHub → `kuashok3/azure-sre-agent-demo` → Settings → Collaborators → add each person; **they must accept the email invite before the session** | The repo is private |
| 0.2 | Check everyone's Azure rights | All developers have admin on the subscription (confirmed 2026-10-13). In Step 1.8 the role must be **Owner** (or Contributor **+** User Access Administrator) | Bicep and the agent wizard create role assignments; **Contributor alone fails** with `AuthorizationFailed` |
| 0.3 | Only if someone has Contributor alone | Create their two groups and make them Owner of just those (commands below) | Not needed when everyone is Owner |
| 0.3b | Safety briefing | Subscription Owner can change or delete **other teams'** resources. Rule: every command uses `-g $RG` / `-g $AGENT_RG`; read the name twice before any `delete` | Shared subscription |
| 0.4 | Agree aliases | 3–8 lowercase letters, unique (e.g. `ravi`, `meena`) | Every name derives from it |
| 0.5 | Trial check | Ask whether anyone has created an Azure SRE Agent before (Shipra, Sneha, Gaury created agents in this subscription) | The 30-day always-on waiver is per account, max 3 agents. Someone without it pays always-on from day 1 |
| 0.6 | Docker Desktop licence | Confirm with IT | Docker Desktop needs a paid licence in larger companies |
| 0.7 | Cost expectation | ≈ $1.5/day per person while running (PostgreSQL, registry, container apps); agents' active usage per question | The `budget-sredemo` budget ($50, tag-filtered) counts **everyone's** resources |

Granting a developer rights only on their own groups (facilitator runs it, only if 0.2 fails):
```powershell
$DEV_ALIAS = "ravi"; $DEV_UPN = "ravi.kumar@relanto.ai"     # change both
foreach ($g in "rg-sredemo-$DEV_ALIAS", "rg-sredemo-$DEV_ALIAS-agent") {
  az group create -n $g -l centralindia --tags Project=AzureSREAgentDemo Environment=NonProduction Owner=$DEV_ALIAS AutoCleanup=ReviewRequired -o none
  az role assignment create --assignee $DEV_UPN --role Owner --scope (az group show -n $g --query id -o tsv) -o none
}
```

---

## Module 1: Tools on every laptop (30 min)

**Goal:** everyone has the same toolset. **Concept:** reproducible environments. The app, scripts and
infrastructure are all code, so every laptop behaves the same.

| Step | Command | What it does |
|---|---|---|
| 1.1 | `winget install --exact --id Microsoft.AzureCLI` | Installs the Azure CLI (`az`), our remote control for Azure. **Close and reopen PowerShell afterwards** |
| 1.2 | `python --version` | Must print **3.12 or newer**. If the Microsoft Store opens instead, install Python from python.org and tick "Add to PATH" |
| 1.3 | `docker info` | Docker Desktop must be **running** (the Engine running message). It's used to run the app locally |
| 1.4 | `git --version` | Git is needed to clone the code |
| 1.5 | `az login` | Opens the browser to sign in with your **@relanto.ai** account |
| 1.6 | `az account show --query "{sub:name, user:user.name}" -o table` | Confirms you're in **Bangalore Azure PayAsYouGo** |
| 1.7 | `az ad signed-in-user show --query userPrincipalName -o tsv` | Must be your company address, **without `#EXT#`**. A personal account can't approve agent actions |
| 1.8 | `az role assignment list --assignee (az ad signed-in-user show --query id -o tsv) --all --query "[].{role:roleDefinitionName, scope:scope}" -o table` | Shows your Azure rights. Need **Owner** on the subscription, or on your own two groups (Module 0.3) |
| 1.9 | `az bicep install` | Installs Bicep, the language our infrastructure templates are written in |
| 1.10 | `az extension add --name log-analytics` | Lets `az` run KQL log queries from the terminal |

✅ **Checkpoint:** every command above succeeds on every laptop.

---

## Module 2: Get the code and run it locally (30 min)

**Goal:** the whole system runs on your laptop with **no Azure at all**. **Concept:** if it doesn't work
locally, it won't work in the cloud. Local is where you learn the app cheaply.

| Step | Command | What it does |
|---|---|---|
| 2.1 | `cd $HOME\Desktop` then `git clone https://github.com/kuashok3/azure-sre-agent-demo.git` | Downloads the code (sign in to GitHub when asked) |
| 2.2 | `cd azure-sre-agent-demo` | **All remaining commands run from this folder** |
| 2.3 | `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` | Creates a Python virtual environment `.venv`, installs libraries, creates your local `.env` from `.env.example` |
| 2.4 | `.\.venv\Scripts\python.exe -m pytest -m "not integration" -q` | Runs **60 unit tests** (no database needed). Expect `60 passed` |
| 2.5 | `docker compose up -d --build` | Builds one container image and starts 4 containers: PostgreSQL, a one-shot `migrate` job, `payment-stub`, `orders-api` |
| 2.6 | `docker compose ps` | Expect postgres / payment-stub / orders-api **healthy** and migrate **Exited (0)** |
| 2.7 | `.\.venv\Scripts\python.exe -m pytest -m integration -q` | 3 tests against the **real** local database. Expect `3 passed` |
| 2.8 | `python scripts\smoke_test.py` | Calls every endpoint once and checks status codes. Expect `ALL CHECKS PASSED` (13 checks) |

**Explore (facilitator demo, 5 min):**
- Browser http://localhost:8080/docs: create an order, then check it out (Swagger UI).
- Browser http://localhost:8080/health/ready: the database is **critical**, payment is **non-critical**.
- Second window: `docker compose logs -f --no-log-prefix orders-api payment-stub`. Every line is JSON. Point out
  that **one checkout has the same `correlation_id` in both services**.

✅ **Checkpoint:** smoke test passes for everyone.

---

## Module 3: Break it locally (30 min)

**Goal:** see each failure *before* we ask an AI to explain it. **Concept:** symptom vs cause, dependency
criticality, error budgets.

| Step | Command | What it does / what to notice |
|---|---|---|
| 3.1 | `python scripts\fault.py list` | Lists the 6 switchable faults. All are off by default, and the API is protected by a token from your `.env` |
| 3.2 | `python scripts\fault.py enable db_connection_failure` | Every DB call fails. Refresh `/health/ready` → **503 not_ready**; creating an order → **503 database_unavailable** |
| 3.3 | `python scripts\fault.py reset` | Turns everything off. **This is "recovery"** |
| 3.4 | `python scripts\fault.py enable payment_latency --param delay_ms=5000` | payment-stub becomes slow. Checkout → **504 after 2 s**; the order stays **PENDING** (safe to retry); readiness still `ready`. **The symptom is in orders-api, the cause is in payment-stub** |
| 3.5 | `python scripts\fault.py reset` | Recover, then retry the same checkout: it succeeds |
| 3.6 | `docker compose stop postgres`, then `docker compose start postgres` | A **real** outage: the error message has **no** "injected fault" hint. After the start, the app recovers by itself within seconds |
| 3.7 | `python scripts\load.py --concurrency 20 --duration 20` | Traffic spike: note the success ratio and p95 latency |
| 3.8 | `python scripts\validate_faults.py --include-docker` | Runs every scenario automatically with pass/fail checks. Expect `ALL SCENARIOS PASSED` |

**Theory slot (5 min):** open `docs\SERVICE_LEVELS.md` §3. A 30% error rate against a 99.5% SLO burns the
error budget **60× faster** than allowed.

✅ **Checkpoint:** `ALL SCENARIOS PASSED`.

---

## Module 4: Azure foundation (45 min)

**Goal:** create your own infrastructure with code. **Concepts:** resource groups as boundaries,
infrastructure as code (Bicep), "what-if" before you spend, managed identities (no passwords).

### 4.1 Session variables: the only step where you type your alias
```powershell
$ALIAS    = "ravi"                                   # <-- YOUR alias, lowercase
$LOCATION = "centralindia"
$RG       = "rg-sredemo-$ALIAS"
$AGENT_RG = "rg-sredemo-$ALIAS-agent"
$PG_SKU   = "Standard_B1ms"
$ME_ID    = az ad signed-in-user show --query id -o tsv
$ME_UPN   = az ad signed-in-user show --query userPrincipalName -o tsv
$MY_IP    = (Invoke-RestMethod https://api.ipify.org)
$TAG      = git rev-parse --short HEAD
"$ALIAS | $RG | $LOCATION | $ME_UPN | $MY_IP | $TAG"
```
**What it does:** stores your names, your identity, your public IP (for the database firewall) and the code
version (used as the image tag). ✅ One line with every value filled in.

### 4.2 Resource group
```powershell
az group create --name $RG --location $LOCATION --tags Project=AzureSREAgentDemo Environment=NonProduction Owner=$ALIAS AutoCleanup=ReviewRequired -o table
```
**What it does:** creates your private container for every app resource. Tags drive cost tracking (the
shared budget counts `Project=AzureSREAgentDemo`) and cleanup. Skip it if the facilitator already created it (0.3).

### 4.3 Preview: creates nothing
```powershell
az deployment group what-if -g $RG -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU
```
**What it does:** shows exactly what Azure *would* create. ✅ `Resource changes: 14 to create`, no Delete/Modify.

### 4.4 Deploy phase 1: about 10–15 min (PostgreSQL is slowest)
```powershell
az deployment group create -g $RG -n phase1 -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU -o table
```
**What it creates:** Log Analytics (0.5 GB/day cost cap), Application Insights, the app's managed identity,
a container registry, Key Vault, PostgreSQL (**passwordless**: Entra sign-in only, you're the admin),
and a Container Apps environment. ✅ `Succeeded`.

**Theory slot while waiting:** open `infra\main.bicep` and walk through it top to bottom; then `docs\ARCHITECTURE.md` §6 (design decisions).

---

## Module 5: Application in Azure (45 min)

**Goal:** the same container image that ran locally now runs in Azure, signs in to the database with its
identity, and sends telemetry. **Concepts:** secrets in Key Vault, cloud image builds, least privilege, releases and rollback.

### 5.0 Load the names Azure generated (re-run after opening a new window)
```powershell
$OUT = az deployment group show -g $RG -n phase1 --query properties.outputs -o json | ConvertFrom-Json
$ACR = $OUT.registryName.value; $KV = $OUT.keyVaultName.value; $PG = $OUT.postgresServerName.value; $PG_FQDN = $OUT.postgresFqdn.value
"$ACR | $KV | $PG"
```

### 5.1 Fault-admin token into Key Vault (never displayed)
```powershell
$bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$TOKEN = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
az keyvault secret set --vault-name $KV --name fault-admin-token --value $TOKEN --output none
Remove-Variable TOKEN, bytes
az keyvault secret show --vault-name $KV --name fault-admin-token --query "attributes.enabled" -o tsv
```
**What it does:** generates a strong random token on your laptop, stores it only in Key Vault, then erases it
from memory. ✅ `true`. `Forbidden` = the new permission is still spreading: wait 2–5 min and repeat.

### 5.2 Build the image in Azure
```powershell
az acr build --registry $ACR --image "sre-demo-app:$TAG" --build-arg APP_VERSION=$TAG --build-arg GIT_SHA=$TAG .
```
**What it does:** uploads the code (without `.env`/`.venv`) and builds the container image **in Azure**. ✅ `... was successful`.

### 5.3 Database setup: migrations + app's least-privilege user
```powershell
.\.venv\Scripts\python.exe scripts\azure_db_bootstrap.py --server-fqdn $PG_FQDN --admin-upn $ME_UPN
```
**What it does:** as the Entra admin, creates the tables, then creates a database user for the app's managed
identity that may **read and write data only**: no TRUNCATE, no schema changes. ✅ Lines `[1/3]`, `[2/3]`, `[3/3]`.

### 5.4 Deploy phase 2: the two apps
```powershell
az deployment group create -g $RG -n phase2 -f infra/main.bicep -p location=$LOCATION deployerObjectId=$ME_ID deployerPrincipalName=$ME_UPN clientIpAddress=$MY_IP postgresSkuName=$PG_SKU deployApps=true imageTag=$TAG gitSha=$TAG -o table
$URL = "https://" + (az deployment group show -g $RG -n phase2 --query properties.outputs.ordersAppFqdn.value -o tsv); $URL
```
**What it does:** same template, now with the apps: `ca-orders-api` (public HTTPS) and `ca-payment-stub`
(**internal only**), 1 replica each. ✅ A URL ending in `.centralindia.azurecontainerapps.io`.

### 5.5 Is it really working?
| Command | What it proves |
|---|---|
| `curl.exe -s "$URL/health/ready"` | `ready`: app started, DB sign-in **with managed identity** works, internal payment-stub reachable, Key Vault secret injected |
| `curl.exe -s "$URL/info"` | Version = your `$TAG`, region `centralindia`, `telemetry_enabled: true` |
| `python scripts\smoke_test.py --base-url $URL` | `ALL CHECKS PASSED` against Azure |

### 5.6 Fault drills in Azure
```powershell
$env:FAULT_ADMIN_TOKEN = az keyvault secret show --vault-name $KV --name fault-admin-token --query value -o tsv
python scripts\validate_faults.py --base-url $URL
python scripts\fault.py reset --base-url $URL
Remove-Item Env:FAULT_ADMIN_TOKEN
```
**What it does:** reads your token from Key Vault into this window only, runs every scenario against Azure,
resets, then **removes the token from the window**. (Leftover token variables broke a script during the build, so always clean up.)
✅ `ALL SCENARIOS PASSED`.

---

## Module 6: Observability: KQL and alerts (40 min)

**Goal:** answer "what is happening?" from telemetry, and get told automatically when it goes wrong.
**Concepts:** logs vs traces vs metrics, KQL, sampling (`ItemCount`), alert rules, time-to-detect.

| Step | Command | What it does |
|---|---|---|
| 6.1 | `powershell -ExecutionPolicy Bypass -File scripts\run_kql.ps1 -ResourceGroup $RG -Lookback 24h` | Runs our 15 validated KQL queries against **your** workspace: errors, latency, dependencies, SLOs, fault audit trail |
| 6.2 | Facilitator: open `kql\20_latency_request_vs_dependency.kql` | Teach: compare request time with dependency time to find **where** time is spent |
| 6.3 | Portal → your `appi-sredemo` → **Logs** → paste any `kql\*.kql` file | Same queries in the UI |
| 6.4 | `az deployment group create -g $RG -n alerts -f infra/alerts.bicep -p alertEmail=$ME_UPN -o table` | Creates an e-mail action group and **4 alert rules**: 5xx rate, p95 latency, dependency failures, database unavailable |
| 6.5 | `az monitor scheduled-query list -g $RG --query "[].{name:name, enabled:enabled}" -o table` | ✅ 4 rules, all enabled |

**Test-fire an alert:**
```powershell
$env:FAULT_ADMIN_TOKEN = az keyvault secret show --vault-name $KV --name fault-admin-token --query value -o tsv
python scripts\fault.py enable http_5xx --param error_rate=0.5 --base-url $URL
python scripts\load.py --base-url $URL --concurrency 2 --duration 180
python scripts\fault.py reset --base-url $URL
Remove-Item Env:FAULT_ADMIN_TOKEN
```
**What it does:** 50% of requests fail for 3 minutes, then everything is restored. Within **5–10 min** the alert
**fires** (facilitator's run: 4½ min) and later **resolves** by itself. Watch Portal → Monitor → Alerts, filtered to your
group. If no e-mail arrives, check Junk and quarantine for `azure-noreply@microsoft.com`.

**Teaching moment:** a few minutes of detection delay is part of every incident's impact.

---

## Module 7: Create your SRE Agent (40 min)

**Goal:** an AI operations agent that can **see** your app but **not change it** without your approval.
**Concepts:** agent identity vs app identity, least privilege, the trial and cost cap.

### 7.1 Wizard at https://sre.azure.com → Create agent
| Field | Value |
|---|---|
| Subscription | Bangalore Azure PayAsYouGo |
| Resource group | **Create new** → `rg-sredemo-<alias>-agent` |
| Agent name | `sre-<alias>` |
| Region | Central India |
| Model provider | default (note which) |
| **User-assigned managed identity** | **Create new**. Never reuse `id-orders-api`: one workload, one identity |
| Application Insights | **Create new**, so the agent's own telemetry stays out of your app's workspace |

### 7.2 Set up your agent → Quickstart tab
| Card | Choose |
|---|---|
| Azure resources | **Resource group** → **your** `rg-sredemo-<alias>` → permission level **Reader** |
| Logs | **Application Insights** → your `appi-sredemo` (in your group) |
| Code | **GitHub** → `kuashok3/azure-sre-agent-demo` |

⛔ **Never** in this shared subscription: Subscription or Management-group scope, **Privileged** level, or the
**Incidents** card / Azure Monitor incident platform. That needs subscription-wide rights, and **every agent would pick up
every alert in the subscription**, including other people's and other teams'.

### 7.3 Remove the extra role the wizard adds
```powershell
$AGENT_MI = az identity list -g $AGENT_RG --query "[0].principalId" -o tsv
az role assignment delete --assignee $AGENT_MI --role "Container Apps Operator" --scope (az group show -n $RG --query id -o tsv)
az role assignment list --assignee $AGENT_MI --all --query "[].{role:roleDefinitionName, scope:scope}" -o table
```
**Why:** at "Reader" level the wizard also grants *Container Apps Operator*, which allows a **shell inside your app
container** (and from there the app's identity and secrets), reading app secrets, and restarts. ✅ Exactly 4 roles remain:
Reader, Monitoring Reader, Log Analytics Reader (your app group) and Monitoring Contributor (your agent group). See `docs\PERMISSIONS.md`.

### 7.4 Tag the agent's resources for the budget
```powershell
az resource list -g $AGENT_RG --query "[].id" -o tsv | ForEach-Object { az tag update --resource-id $_ --operation merge --tags Project=AzureSREAgentDemo Environment=NonProduction Owner=$ALIAS AutoCleanup=ReviewRequired -o none }
```

### 7.5 In the agent portal
| Where | Do |
|---|---|
| Settings → Agent consumption → Change AAU allocation | **500** (minimum). Caps active usage; measured ≈ 8–10 AAU per question |
| Banner at the top | Note the trial end date and put it in your calendar. **Delete the agent before that date** unless you decide to keep it |
| **Builder → Knowledge base** | Upload: all 5 `runbooks\*.md`; `agent-context\AGENT_INSTRUCTIONS.md`, `RESOURCE_BOUNDARIES.md`; `docs\SYSTEM_OVERVIEW.md`, `ARCHITECTURE.md`, `KNOWN_FAILURE_MODES.md`, `SERVICE_LEVELS.md`, `OBSERVABILITY.md`. **Developers: skip** `RESOURCE_INVENTORY.md` and `PERMISSIONS.md`, which list the facilitator's resource names |
| **Chat** (first message) | Tell the agent which environment is yours (the docs mention the facilitator's `rg-sredemo-app`):<br>`#remember My application resource group is rg-sredemo-<alias> and my agent resource group is rg-sredemo-<alias>-agent. References to rg-sredemo-app in the documentation are the facilitator's environment; always use my resource group.` |

**Careful in pickers:** every person's App Insights is named `appi-sredemo` and every workspace `log-sredemo`.
Always choose the one whose **resource group** is yours.

✅ **Checkpoint:** all three cards are green, 4 roles remain, the knowledge base has 12 files, the `#remember` is saved.

---

## Module 8: Test the agent (40 min)

**Goal:** learn to **verify** an AI's answers, not admire them. **Concept:** every claim needs evidence.
Absence of evidence counts only if the query was right.

Use `agent-context\tests\LEVEL_1_2.md`. **Replace `rg-sredemo-app` with your own group** in the prompts.
One new chat thread per prompt. Recommended set for the session:

| ID | Prompt | What a good answer contains |
|---|---|---|
| L1-01 | `What does the application in resource group rg-sredemo-<alias> do? Cite your sources.` | Contoso Orders, orders-api + payment-stub + PostgreSQL; cites README |
| L1-02 | `List every Azure resource in rg-sredemo-<alias> (query it fresh) and say which ones host the application.` | The **9** application resources (workspace, App Insights, identity, registry, Key Vault, PostgreSQL, `cae-sredemo`, the two container apps), plus Module 6's alerting (action group, 4 alert rules, possibly an auto-created "Failure Anomalies" rule). Must name `cae-sredemo` as the environment hosting both apps. Cross-check: `az resource list -g $RG -o table` |
| L2-01 | `Find errors from orders-api in the last 24 hours. Group them by status code and error code, show the KQL you used, and tell me whether any were caused by fault injection.` | 500s/503s/504 from your drills; recognises the `fault_enabled` events |
| L2-03 | `What is orders-api's error rate right now (last 15 minutes)? Is anything currently broken?` | Healthy/idle now; doesn't report old drills as live |

**Verify every answer:** run the matching `kql\` file (`scripts\run_kql.ps1 -ResourceGroup $RG -Name <file>`) and compare the numbers.

**Known agent mistake, worth showing** (facilitator's L2-03): it searched for `fault_reset` (doesn't exist; the real
event is `faults_reset`), concluded the fault was "still active", and **invented** an endpoint `POST /admin/faults/reset`
(the real one is `DELETE /admin/faults`). Right numbers, wrong conclusion.

**Tuning (then re-run L2-03):** paste into a chat:
```text
#remember Fault-injection audit events in AppTraces Properties.event are exactly: fault_enabled, fault_disabled, faults_reset (plural). Use kql/03_fault_audit_trail.kql.
#remember The fault API is DELETE /admin/faults (reset all) and requires a token you do not have; never suggest other endpoints.
#remember Before concluding an event did NOT happen, first list the distinct Properties.event values to confirm the exact name.
```

---

## Module 9: Incident exercise (45–60 min)

**Goal:** a realistic incident, end to end: break, detect, investigate with the agent, mitigate, verify, write it up.
Each developer runs it in their **own** environment. **The agent recommends; humans decide.**

### 9A: Dependency timeout (the "symptom vs cause" incident)
1. **Break it** (facilitator says go; note the UTC time):
```powershell
$env:FAULT_ADMIN_TOKEN = az keyvault secret show --vault-name $KV --name fault-admin-token --query value -o tsv
python scripts\fault.py enable payment_latency --param delay_ms=5000 --base-url $URL
python scripts\load.py --base-url $URL --concurrency 4 --duration 300
```
**What it does:** payment-stub becomes slow; checkouts time out (504) while everything else works.
2. **Detect:** wait for the alert e-mail or Portal → Monitor → Alerts (`5xx rate` and/or `dependency failures`).
3. **Investigate with the agent** (new thread):
```text
Alert "orders-api: 5xx error rate above 5%" fired a few minutes ago for resource group rg-sredemo-<alias>.
Investigate: which endpoints fail and with which codes, whether the cause is in orders-api or a dependency
(compare orders-api's dependency calls with payment-stub's own requests), whether fault injection is involved,
the customer impact, and the error-budget burn rate (SLO 99.5%). Give the root cause with a confidence level and
the evidence (KQL + results). Recommend a mitigation from our runbooks. Do NOT execute any change.
```
4. **Grade it**: expected: checkout 504 `payment_service_timeout`; orders-api's calls to payment-stub fail at ~2 s
while payment-stub's own requests take ~5 s, so **cause = payment-stub slowness**; `fault_enabled payment_latency` audit event;
other endpoints healthy; runbook `DEPENDENCY_TIMEOUT.md`; mitigation = reset the fault (a human action: the agent has no token).
Check its numbers with `scripts\run_kql.ps1 -ResourceGroup $RG -Name 25_payment_orders_view` and `-Name 26_payment_stub_own_view`.
5. **Mitigate and verify:**
```powershell
python scripts\fault.py reset --base-url $URL
Remove-Item Env:FAULT_ADMIN_TOKEN
python scripts\smoke_test.py --base-url $URL
```
Then confirm the alert **resolves by itself** (not silenced).
6. **Write it up:** fill in the template in `docs\INCIDENT_RESPONSE.md`, including "Was the agent's RCA correct?".

### 9B (optional): a REAL outage, with no injected hints
```powershell
az postgres flexible-server stop -g $RG -n $PG          # takes a few minutes
python scripts\load.py --base-url $URL --concurrency 2 --duration 240
```
Ask the agent: `orders-api is failing. Find the root cause and evidence, and propose a fix. Do not execute anything without my approval.`
A good agent finds `database_unavailable` and that **the PostgreSQL server is Stopped**, and proposes starting it. Because
its identity is Reader-only, it must **ask for your approval** (on-behalf-of). Approving is safe here: it's your own
environment. Or start it yourself: `az postgres flexible-server start -g $RG -n $PG`. Verify with `curl.exe -s "$URL/health/ready"`.

---

## Module 10: Cost routine and cleanup (15 min)

| Choice | Commands | Effect |
|---|---|---|
| **Pause** (continue practising later) | `az postgres flexible-server stop -g $RG -n $PG`; `az containerapp update -n ca-orders-api -g $RG --min-replicas 0`; same for `ca-payment-stub` | Stops most compute cost. **The agent's trial clock keeps running** |
| **Resume** | `az postgres flexible-server start -g $RG -n $PG`, then re-run **5.4** | Back to 1 replica each |
| **Delete everything** (end of training) | `az group delete -n $AGENT_RG --yes --no-wait` (deleting the agent stops all its billing); `az group delete -n $RG --yes`; `az keyvault purge --name $KV --location $LOCATION` | Removes your app, database, registry, telemetry, agent |

Verify nothing is left (after the deletes finish, ~5–10 min):
`az group list --query "[?starts_with(name, 'rg-sredemo-$ALIAS')].name" -o tsv` should print nothing.

---

## Appendix A: Troubleshooting (all seen for real while building this)

| Symptom | Cause | Fix |
|---|---|---|
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Another local app uses the port | In `.env` set `ORDERS_HOST_PORT`/`PAYMENT_HOST_PORT`/`POSTGRES_HOST_PORT`, adjust `DB_PORT` and `PAYMENT_BASE_URL`, and use `--base-url` with scripts |
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop not running | Start it and wait for "Engine running" |
| PostgreSQL `SkuNotAvailable` | Size not offered in that region for this subscription | Keep `centralindia`; don't switch region |
| `azure_db_bootstrap.py` error about `FAULT_ADMIN_TOKEN` placeholder | Old script version + leftover `FAULT*` variables in the window | `git pull`; `Remove-Item Env:FAULTS_ENABLED, Env:FAULT_ADMIN_TOKEN` |
| Script runs from `scripts\` and fails | Wrong folder | `cd` back to the repo root |
| `Forbidden` on Key Vault right after phase 1 | New role still propagating | Wait 2–5 min, retry |
| Step 5.3 timeout / connection refused | Your public IP changed (VPN/Wi-Fi) | Re-run 4.1 (new `$MY_IP`), then 4.4 to update the firewall rule |
| `$URL`, `$KV` etc. are empty | New PowerShell window | Re-run 4.1 and 5.0 |
| KQL error "Query could not be parsed at 'first'" | `first`/`last` are reserved words in KQL | Name columns `first_seen` / `last_seen` |
| Text turns into `âœ…`-style garbage after editing a file with PowerShell | PowerShell 5 reads UTF-8 as ANSI | Edit files in VS Code, not with `Get-Content`/`Set-Content` |
| Alert fired but no e-mail | Company mail filter | Check Junk/quarantine; allow `azure-noreply@microsoft.com` |
| Agent says "Access required" / 403 | No SRE Agent role on that agent | The creator gets Administrator automatically; others need a role on the agent (IAM) |
