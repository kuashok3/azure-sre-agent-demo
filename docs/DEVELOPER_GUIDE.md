# Developer Guide: Contoso Orders

The big picture, how to try the app in Swagger, what every script does, the `.env` question, and
troubleshooting. For the step-by-step session plan see [TRAINING_RUNBOOK.md](TRAINING_RUNBOOK.md).

---

## 1. Big picture: the whole system

```
 ┌──────────────────────────── DEVELOPER LAPTOP ─────────────────────────────┐
 │  VS Code / PowerShell                                                     │
 │   ├─ git clone ◄──────────────────────────── GitHub (private repo) ───────┼──┐ code, docs,
 │   ├─ scripts\*.py  (smoke, faults, load)                                  │  │ runbooks
 │   └─ docker compose (LOCAL MODE, no Azure needed)                         │  │
 │        browser/Swagger :8080 ─► orders-api ─HTTP─► payment-stub :8081     │  │
 │                                     └──SQL──► PostgreSQL :5434            │  │
 │   az CLI + Bicep ──────────── deploys ──────────────┐                     │  │
 └─────────────────────────────────────────────────────┼─────────────────────┘  │
                                                       ▼                        │
 ┌──────────────── AZURE: rg-sredemo-<alias> (Central India) ────────────────┐  │
 │  Container Apps environment (cae-sredemo)                                 │  │
 │    ca-orders-api  (public HTTPS) ──HTTP──► ca-payment-stub (internal only)│  │
 │        │  signs in with its managed identity id-orders-api (no passwords) │  │
 │        ├──SQL (Entra token)──► PostgreSQL Flexible Server (psql-…)        │  │
 │        └──reads token────────► Key Vault (kv-…)  image from ► ACR (cr…)   │  │
 │  Both apps ──telemetry──► Application Insights ─► Log Analytics           │  │
 │                                       │  (requests, dependencies, logs)   │  │
 │  Alert rules (5xx, latency, dependency, database) ──► e-mail you          │  │
 └───────────────────────────────────────┬───────────────────────────────────┘  │
                                         │ reads (Reader only)                  │
 ┌───────────── AZURE: rg-sredemo-<alias>-agent ─────────────┐                  │
 │  Azure SRE Agent (sre-<alias>), its own managed identity   │◄────────────────┘
 │  knowledge base (runbooks, docs) · chat at sre.azure.com   │  GitHub connector
 │  proposes fixes → YOU approve any change                   │
 └────────────────────────────────────────────────────────────┘
```

**One sentence:** the same container image runs locally and in Azure; Azure records everything it does;
the SRE Agent reads that evidence plus our code and runbooks, and recommends actions that a human approves.

| Concept | Local | Azure |
|---|---|---|
| Run the apps | `docker compose` | Container Apps |
| Database login | user + password from `.env` | **managed identity** (no password exists) |
| Secrets | `.env` (local placeholders) | Key Vault |
| Logs | `docker compose logs` | Application Insights / Log Analytics (KQL) |
| Who investigates | you | you **and** the SRE Agent |

---

## 2. The `.env` question

**Q: When I clone from GitHub, `.env` is missing. Do I have to create it?**
**A: No manual work. `scripts\setup.ps1` creates it for you** by copying `.env.example`.

| File | In git? | What it is |
|---|---|---|
| `.env.example` | ✅ yes | The template, with **local-only placeholder values** (e.g. `DB_PASSWORD=local-dev-only-password`). Safe to share |
| `.env` | ❌ **never** (in `.gitignore`) | Your personal copy. Read by docker compose and the scripts. Each developer has their own |

- The defaults work as they are on any laptop where ports 8080, 8081 and 5434 are free.
- Edit `.env` only to change ports (see §6), and then run `docker compose up -d` again.
- **Azure does not use `.env`.** In Azure, settings come from the Container App configuration and the fault
  token comes from Key Vault. The placeholder token `change-me…` is **rejected** when `ENVIRONMENT=azure`.
- If `.env` was deleted: `Copy-Item .env.example .env`.

---

## 3. Testing the app with Swagger (local)

Open **http://localhost:8080/docs**. For any endpoint: click it → **Try it out** → edit → **Execute**. Below the
result Swagger shows the **status code**, the **response body** and the **response headers**. Note
`x-correlation-id` and `x-response-time-ms` there.

### 3.1 Is it healthy?
| Endpoint | Expected |
|---|---|
| `GET /health/live` | `200` `{"status":"alive"}` |
| `GET /health/ready` | `200` `{"status":"ready", "checks": {"database": {...ok}, "payment_service": {...ok}}}` |
| `GET /info` | version, environment `local`, `faults_enabled: true` |

### 3.2 Happy path: create, then pay
1. **`POST /api/v1/orders`** with body:
   ```json
   {"customer_id": "cust-001", "currency": "USD",
    "items": [{"sku": "WIDGET-1", "quantity": 2, "unit_price_cents": 1250},
              {"sku": "GADGET-2", "quantity": 1, "unit_price_cents": 4999}]}
   ```
   → **201**, `status: PENDING`, `total_cents: 7499`. **Copy the `id`.**
2. **`GET /api/v1/orders/{order_id}`** with that id → **200**, same order with its items.
3. **`POST /api/v1/orders/{order_id}/checkout`** → **200**, `status: PAID`, `payment_reference: pay_…`.
4. **`GET /api/v1/orders`** → the new order is first. **`GET /api/v1/stats`** → `PAID` count went up.

### 3.3 Expected "errors" (the app behaving correctly)
| Try | Expected | Lesson |
|---|---|---|
| Checkout the **same** order again | **409** `order_state_conflict` | No double payment |
| `GET /api/v1/orders/{order_id}` with a random UUID, e.g. `11111111-1111-1111-1111-111111111111` | **404** `order_not_found`, body includes `correlation_id` | Error bodies always carry the correlation ID |
| `GET /api/v1/orders/{order_id}` with `abc` | **422** | Input validated before any code runs |
| Create with `"quantity": 0` or `"items": []` | **422** with field details | Validation rules |
| Create with `"unit_price_cents": 2000000` (= $20,000), then checkout | **402** `payment_declined`; order becomes `PAYMENT_FAILED` | A **business** outcome, **not an outage**. It doesn't count against the SLO |

### 3.4 Break it from Swagger (fault injection)
On every `/admin/faults` call, fill the **`x-fault-token`** field with the token from your `.env`
(locally: `change-me-local-fault-token`). Without it you get **401**.
| Step | Call | Then observe |
|---|---|---|
| 1 | `GET /admin/faults` | 6 available faults, `active: []` |
| 2 | `PUT /admin/faults/{name}` with name `latency`, body `{"params": {"delay_ms": 1500}}` | Any `/api/v1/...` call now takes ~1.5 s (see `x-response-time-ms`); `/health/live` stays fast |
| 3 | `PUT /admin/faults/{name}` with name `db_connection_failure`, body `{}` | Create order → **503** `database_unavailable`; `/health/ready` → **503** |
| 4 | `PUT /admin/faults/{name}` with name `payment_latency`, body `{"params": {"delay_ms": 5000}}` | Checkout → **504** after 2 s; the order stays `PENDING` |
| 5 | **`DELETE /admin/faults`** | **Recovery**: everything off. Repeat the happy path |

Watch it happen: `docker compose logs -f --no-log-prefix orders-api payment-stub` in a second window.

---

## 4. What every script does

All scripts run from the **repo root**. The `.py` helpers in `scripts\` use only Python's standard library
(except `azure_db_bootstrap.py`, which needs the `.venv`).

| Script | What it does | When you use it | Example |
|---|---|---|---|
| `scripts\setup.ps1` / `setup.sh` | Creates `.venv`, installs libraries, creates `.env` from `.env.example` | Once, after cloning | `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` |
| `scripts\smoke_test.py` | Calls every endpoint once and checks status codes (13 checks) | After any start or deploy | `python scripts\smoke_test.py` · `--base-url $URL` for Azure |
| `scripts\fault.py` | Lists, enables, disables or resets faults through `/admin/faults` (token from `.env` or `FAULT_ADMIN_TOKEN`) | Manual drills | `python scripts\fault.py enable latency --param delay_ms=1500` · `python scripts\fault.py reset` |
| `scripts\validate_faults.py` | Runs **every** fault scenario, checks the symptom **and** the recovery, prints PASS/FAIL | Prove failure behaviour; demos | `python scripts\validate_faults.py` · `--include-docker` adds real outages locally |
| `scripts\load.py` | Generates traffic for N seconds; prints req/s, status codes, success ratio, p50/p95/p99 | Traffic spikes; make alerts fire | `python scripts\load.py --concurrency 20 --duration 30` |
| `scripts\run_kql.ps1` | Runs the saved queries in `kql\` against your Log Analytics workspace | Investigate in Azure; check the agent's numbers | `powershell -ExecutionPolicy Bypass -File scripts\run_kql.ps1 -ResourceGroup $RG -Lookback 24h` |
| `scripts\azure_db_bootstrap.py` | **Azure only, once:** creates tables (as you, the DB admin) and a data-only DB user for the app's identity | Module 5 | `.\.venv\Scripts\python.exe scripts\azure_db_bootstrap.py --server-fqdn $PG_FQDN --admin-upn $ME_UPN` |
| `scripts\_common.py` | Shared helper for the scripts (HTTP calls, reading `.env`) | Not run directly | — |
| `python -m app.orders.migrate` | Applies `migrations\*.sql` once each (the `migrate` container runs it locally) | Automatic | — |
| `python -m app.common.healthcheck` | Docker's health probe: calls `/health/live` | Automatic | — |

Other folders: `kql\` (15 validated queries, each with the question it answers), `infra\` (Bicep: `main.bicep`
app + infrastructure, `alerts.bicep` alerting, `budget.bicep` budget), `api\requests.http` (the same requests as §3
for the VS Code REST Client).

---

## 5. Automated tests

| Command | What it runs |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -m "not integration"` | **60 unit tests**: business rules, error codes, health logic, fault switches, config validation, telemetry setup. No database, ~2 s. Hermetic (ignores your shell's env vars) |
| `.\.venv\Scripts\python.exe -m pytest -m integration` | **3 tests** against the real local PostgreSQL (needs `docker compose up`) |
| `.\.venv\Scripts\python.exe -m ruff check .` | Lint (style and bug patterns) |
| GitHub Actions `ci.yml` | Runs lint + unit + integration + image build on every push to `main` |

---

## 6. Troubleshooting

### Local
| Symptom | Likely cause | Fix |
|---|---|---|
| `python` opens the Microsoft Store | Windows app alias, Python not installed | Install Python 3.12+ from python.org, tick "Add to PATH"; reopen PowerShell |
| `setup.ps1 cannot be loaded … execution policy` | PowerShell script policy | Use exactly `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` |
| `error during connect … dockerDesktopLinuxEngine` | Docker Desktop not running | Start Docker Desktop, wait for "Engine running" |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Another app uses the port | In `.env` set `ORDERS_HOST_PORT=8090` (and/or `PAYMENT_HOST_PORT`, `POSTGRES_HOST_PORT`; keep `DB_PORT` = `POSTGRES_HOST_PORT` and `PAYMENT_BASE_URL` on the new payment port); `docker compose up -d`; scripts: `--base-url http://localhost:8090` |
| `Set DB_PASSWORD in .env` | No `.env` | `Copy-Item .env.example .env` |
| `migrate` exited with an error / orders-api not starting | DB not ready, or broken migration | `docker compose logs migrate`; `docker compose up -d` again |
| `/health/ready` → 503 | DB down, or a `db_*` fault active | `python scripts\fault.py list`; `docker compose ps`; `python scripts\fault.py reset` |
| Requests slow / failing for no reason | A fault is still active | `python scripts\fault.py list` then `reset` |
| `401` from fault.py or Swagger | Wrong / missing token | Token must equal `FAULT_ADMIN_TOKEN` in `.env`; after editing `.env` run `docker compose up -d` |
| Integration tests "skipped" | PostgreSQL not running | `docker compose up -d` first |
| Need a clean start | Old data or state | `docker compose down -v` (deletes local DB data), then `docker compose up -d --build` |
| Garbled characters (`âœ…`) after editing a file | PowerShell 5 rewrote UTF-8 | Edit in VS Code; `git checkout -- <file>` to undo |

### Useful look-around commands
| Command | Shows |
|---|---|
| `docker compose ps` | Which containers run and whether they're healthy |
| `docker compose logs -f --no-log-prefix orders-api` | Live JSON logs |
| `docker compose logs migrate` | Database migration output |
| `curl.exe -s http://localhost:8080/health/ready` | Dependency health in one line |

Azure-side errors (Key Vault `Forbidden`, `SkuNotAvailable`, firewall/IP changes, empty variables in a new window)
are in [TRAINING_RUNBOOK.md](TRAINING_RUNBOOK.md) Appendix A and [DEPLOYMENT.md](DEPLOYMENT.md) §4.
