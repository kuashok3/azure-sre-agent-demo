# Contoso Orders — Azure SRE Agent learning project

A small order-processing service that we run locally, deploy to Azure Container Apps, observe with
Application Insights, and then investigate with **Azure SRE Agent** while injecting controlled
failures.

| Doc | Purpose |
|---|---|
| [docs/00_PHASE0_BLUEPRINT.md](docs/00_PHASE0_BLUEPRINT.md) | Verified SRE Agent capabilities, architecture, roadmap, costs |
| [CHECKPOINTS.md](CHECKPOINTS.md) | Milestone status and open issues |
| [SECURITY.md](SECURITY.md) | Secrets, fault-API safety, least privilege |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching, checks, conventions |

## What runs

```
           :8080                       :8081 (internal in Azure)
client ──► orders-api (FastAPI) ──HTTP──► payment-stub (FastAPI)
               │
               └──SQL──► PostgreSQL 16 (:5434 on the host)
```

| Service | Purpose | Key endpoints |
|---|---|---|
| orders-api | Create, view, check out orders | `/`, `/health/live`, `/health/ready`, `/info`, `/api/v1/orders`, `/api/v1/orders/{id}`, `/api/v1/orders/{id}/checkout`, `/api/v1/stats`, `/docs` |
| payment-stub | Fake payment processor (approves ≤ $10,000, declines above) | `/api/v1/payments`, `/health/live` |
| migrate | One-shot job that applies `migrations/*.sql` | — |

Both apps come from the same container image. Logs are JSON on stdout. Every request gets an
`X-Correlation-ID`, which is passed to payment-stub too.

---

## Local quick start (Windows PowerShell)

### Step 1: Install prerequisites
| Tool | Version | Check |
|---|---|---|
| Python | 3.12 or newer | `python --version` |
| Docker Desktop | running, Linux containers | `docker info` |
| Git | any recent | `git --version` |

### Step 2: Create the environment
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
**Expected:** `Setup complete.` This creates `.venv` and a local `.env` (git-ignored).
Linux/macOS: `bash scripts/setup.sh`.

### Step 3: Run the unit tests (no Docker needed)
```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```
**Expected:** `53 passed, 3 deselected`.

### Step 4: Start the stack
```powershell
docker compose up -d --build
docker compose ps
```
**Expected:** `postgres`, `payment-stub` and `orders-api` show `running (healthy)`. `migrate` shows
`Exited (0)`.

### Step 5: Integration tests and smoke test
```powershell
.\.venv\Scripts\python.exe -m pytest -m integration
python scripts\smoke_test.py
```
**Expected:** `3 passed` and `ALL CHECKS PASSED` (13 checks).

### Step 6: Explore
- Swagger UI: http://localhost:8080/docs
- Readiness: http://localhost:8080/health/ready
- Logs: `docker compose logs -f orders-api` (each line is JSON with `correlation_id`)
- Example requests: [api/requests.http](api/requests.http)

### Step 7: Trigger each failure and confirm recovery
```powershell
python scripts\fault.py list
python scripts\validate_faults.py                   # all synthetic faults, with recovery checks
python scripts\validate_faults.py --include-docker  # adds REAL outages (stops/starts containers)
python scripts\load.py --concurrency 20 --duration 30   # traffic spike
```
**Expected:** `ALL SCENARIOS PASSED`.

To do it by hand:
```powershell
python scripts\fault.py enable latency --param delay_ms=1500
curl.exe -s -o NUL -w "%{http_code} %{time_total}s`n" http://localhost:8080/api/v1/orders
python scripts\fault.py reset
```

| Fault | Symptom | Recovery |
|---|---|---|
| `latency` | `/api/*` slow (health is not) | `fault.py reset` |
| `http_5xx` | `/api/*` → 500 `internal_error` | `fault.py reset` |
| `db_connection_failure` | 503 `database_unavailable`, readiness 503 | `fault.py reset` |
| `db_latency` | DB-backed calls slow | `fault.py reset` |
| `payment_latency` | checkout → 504 after 2 s, order stays PENDING | `fault.py reset` |
| `payment_errors` | checkout → 503 | `fault.py reset` |
| Real DB outage | `docker compose stop postgres` → 503 | `docker compose start postgres` |
| Real payment outage | `docker compose stop payment-stub` → readiness `degraded`, checkout 503 | `docker compose start payment-stub` |
| Traffic spike | `scripts/load.py` → latency rises | stop the script |

Synthetic faults say "injected fault" in their error messages and log `event=fault_enabled`.
The real outages give no such hint, which makes them the better test for an investigator.

### Step 8: Stop
```powershell
docker compose down        # keeps database data
docker compose down -v     # also deletes database data
```

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Another app uses the port | Set `ORDERS_HOST_PORT`, `PAYMENT_HOST_PORT` or `POSTGRES_HOST_PORT` in `.env`, then also update `DB_PORT`/`PAYMENT_BASE_URL` and use `--base-url` with the scripts |
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop not running | Start Docker Desktop and wait until it says "Engine running" |
| `Set DB_PASSWORD in .env` | No `.env` | Run Step 2 (or `Copy-Item .env.example .env`) |
| `migrate` exited non-zero | DB not ready or bad SQL | `docker compose logs migrate` |
| Readiness 503 | DB down or a `db_*` fault active | `python scripts\fault.py list`, `docker compose ps` |
| Integration tests "skipped" | Postgres not running or not migrated | Step 4 first |
| `401 unauthorized` from fault.py | Token mismatch | Token in `.env` must match the running containers; after editing `.env` run `docker compose up -d` |
